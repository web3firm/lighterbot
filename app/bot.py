"""
Main Bot Controller - Master orchestrator for LighterBot
Coordinates all components and manages the main trading loop
"""

import asyncio
import logging
import signal
import sys
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Suppress httpx logs that expose sensitive tokens in URLs
logging.getLogger("httpx").setLevel(logging.WARNING)

# Component imports
from app.lighter.lighter_client import LighterClient
from app.lighter.lighter_order_manager import LighterOrderManager
from app.lighter.lighter_websocket import LighterWebSocket
from app.lighter.market_data import MarketData
from app.lighter.trailing_stop_manager import TrailingStopManager
from app.strategies.strategy_manager import StrategyManager
from app.risk.risk_manager import RiskManager
from app.utils.trading_logger import TradingLogger
from app.utils.error_handler import get_error_handler
from app.telegram_bot import TelegramBot
from app.database.db_manager import DatabaseManager
from ml.auto_trainer import AutoTrainer

logger = logging.getLogger(__name__)


class LighterBot:
    """
    Main trading bot controller
    Implements 1-second main loop with component coordination
    """
    
    def __init__(self):
        """Initialize bot"""
        self.symbol = os.getenv('TRADING_SYMBOL', 'ETH-USD')
        self.market_id = int(os.getenv('LIGHTER_MARKET_ID', '0'))
        
        # Components
        self.lighter_client: Optional[LighterClient] = None
        self.order_manager: Optional[LighterOrderManager] = None
        self.websocket: Optional[LighterWebSocket] = None
        self.market_data: Optional[MarketData] = None
        self.trailing_manager: Optional[TrailingStopManager] = None
        self.strategy_manager: Optional[StrategyManager] = None
        self.risk_manager: Optional[RiskManager] = None
        self.auto_trainer: Optional[AutoTrainer] = None
        self.trading_logger: Optional[TradingLogger] = None
        self.telegram_bot: Optional[TelegramBot] = None
        self.db_manager: Optional[DatabaseManager] = None
        
        # State
        self.running = False
        self.loop_count = 0
        self.last_account_update = datetime.now(timezone.utc)
        self.last_ml_check = datetime.now(timezone.utc)
        self.account_state: Dict[str, Any] = {}
        self.current_position: Optional[Dict[str, Any]] = None
        self.position_lock = asyncio.Lock()  # Prevent race condition when opening positions
        self.last_position_close_time: Optional[datetime] = None
        self.position_cooldown_seconds = int(os.getenv('POSITION_COOLDOWN_SECONDS', '300'))  # Default 5 minutes cooldown
        self.min_position_duration = 60  # Minimum 60 seconds before position can close (prevent instant close bug)
        
        # Statistics
        self.stats = {
            'start_time': datetime.now(timezone.utc),
            'signals_generated': 0,
            'signals_accepted': 0,
            'signals_rejected': 0,
            'positions_opened': 0,
            'positions_closed': 0
        }
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("🤖 LighterBot initializing...")
    
    async def initialize(self):
        """Initialize all components"""
        try:
            logger.info("📦 Initializing components...")
            
            # Initialize trading logger
            self.trading_logger = TradingLogger()
            
            # Initialize Lighter client
            self.lighter_client = LighterClient(
                api_url=os.getenv('LIGHTER_API_URL'),
                api_private_key=os.getenv('LIGHTER_API_PRIVATE_KEY'),
                api_key_index=int(os.getenv('LIGHTER_API_KEY_INDEX', '0')),
                account_index=int(os.getenv('LIGHTER_ACCOUNT_INDEX', '0'))
            )
            if not await self.lighter_client.connect():
                logger.error("❌ Failed to connect to Lighter Protocol. Check your .env credentials!")
                return False
            
            # Initialize order manager (Native SDK)
            self.order_manager = LighterOrderManager(self.lighter_client)
            logger.info("✅ Order Manager initialized (Native SDK OCO)")
            
            # Explicitly set leverage on startup (Crucial for aggressive strategy)
            # This ensures the exchange account is actually set to the desired leverage
            max_leverage = int(os.getenv('MAX_LEVERAGE', '5'))
            if max_leverage > 0:
                logger.info(f"⚙️  Setting account leverage to {max_leverage}x...")
                await self.order_manager.update_leverage(max_leverage, margin_mode='cross')
            
            # Initialize WebSocket (Native SDK)
            self.websocket = LighterWebSocket(
                api_url=os.getenv('LIGHTER_API_URL'),
                account_index=int(os.getenv('LIGHTER_ACCOUNT_INDEX', '0'))
            )
            logger.info("✅ WebSocket initialized (Native SDK)")
            
            # Initialize market data (Native SDK)
            self.market_data = MarketData(self.lighter_client.api_client)
            logger.info("✅ Market Data initialized (Native SDK)")
            
            # Initialize trailing stop manager
            self.trailing_manager = TrailingStopManager(
                self.lighter_client.signer_client,
                price_precision=2
            )
            logger.info("✅ Trailing Stop Manager initialized")
            
            # Initialize database (optional)
            db_url = os.getenv('DATABASE_URL')
            if db_url:
                try:
                    from app.database.db_manager import _db_manager as db_module
                    self.db_manager = DatabaseManager()
                    await self.db_manager.connect()
                    await self.db_manager._initialize_schema()
                    # Set global instance for Telegram commands
                    import app.database.db_manager as db_mod
                    db_mod._db_manager = self.db_manager
                    logger.info("✅ Database connected and initialized")
                except Exception as e:
                    logger.warning(f"⚠️  Database connection failed: {e}")
                    logger.info("ℹ️  Running without database persistence")
            else:
                logger.info("ℹ️  DATABASE_URL not set, running without persistence")
            
            # Initialize Telegram bot (optional)
            telegram_enabled = os.getenv('TELEGRAM_NOTIFICATIONS_ENABLED', 'false').lower() == 'true'
            if telegram_enabled:
                try:
                    self.telegram_bot = TelegramBot(bot_instance=self)
                    await self.telegram_bot.start_bot()
                    logger.info("✅ Telegram bot started")
                except Exception as e:
                    logger.warning(f"⚠️  Telegram bot failed to start: {e}")
                    logger.info("ℹ️  Running without Telegram notifications")
            else:
                logger.info("ℹ️  Telegram notifications disabled in config")
            
            # Initialize ML auto-trainer
            self.auto_trainer = AutoTrainer()
            ml_status = "V2 (Active)" if self.auto_trainer.is_ml_active() else "V1 (Collection)"
            logger.info(f"🤖 ML Phase: {ml_status}")
            
            # Initialize strategy manager with config from env
            strategy_config = {
                'tp_pnl_pct': float(os.getenv('TP_PNL_PCT', '15')),
                'sl_pnl_pct': float(os.getenv('SL_PNL_PCT', '5')),
                'max_leverage': int(os.getenv('MAX_LEVERAGE', '5'))
            }
            self.strategy_manager = StrategyManager(
                self.symbol, 
                strategy_config,
                self.auto_trainer
            )
            
            # Initialize risk manager with config from env
            risk_config = {
                'risk_limits': {
                    'max_position_size_pct': float(os.getenv('POSITION_SIZE_PCT', '50')),
                    'max_positions': int(os.getenv('MAX_OPEN_POSITIONS', '1')),
                    'max_leverage': int(os.getenv('MAX_LEVERAGE', '5')),
                    'max_daily_loss_pct': float(os.getenv('MAX_DAILY_LOSS_PCT', '10'))
                },
                'kill_switch': {
                    'daily_loss_limit_pct': float(os.getenv('MAX_DAILY_LOSS_PCT', '10'))
                },
                'drawdown': {
                    'warning_threshold_pct': float(os.getenv('DRAWDOWN_WARNING_PCT', '5')),
                    'critical_threshold_pct': float(os.getenv('MAX_DRAWDOWN_PCT', '10'))
                }
            }
            self.risk_manager = RiskManager(risk_config)
            
            # Get initial account state
            self.account_state = await self.lighter_client.get_account_state()
            starting_equity = Decimal(str(self.account_state.get('account_value', 0)))
            
            # Initialize risk session
            self.risk_manager.initialize_session(starting_equity)
            
            logger.info("✅ All components initialized")
            logger.info(f"💰 Starting equity: ${starting_equity:.2f}")
            logger.info(f"📊 Trading symbol: {self.symbol}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            return False
    
    async def start(self):
        """Start the bot"""
        logger.info("🚀 Starting LighterBot...")
        
        # Initialize components
        if not await self.initialize():
            logger.error("❌ Initialization failed, cannot start")
            return
        
        self.running = True
        
        # Startup observation period (analyze market without trading)
        startup_delay = int(os.getenv('STARTUP_DELAY_SECONDS', '60'))
        if startup_delay > 0:
            logger.info(f"👀 Observation mode: Analyzing market for {startup_delay}s before trading...")
            self.last_position_close_time = datetime.now(timezone.utc)  # Block trading temporarily
            await asyncio.sleep(startup_delay)
            self.last_position_close_time = None  # Allow trading now
            logger.info("✅ Observation complete - Trading enabled")
        
        logger.info("✅ Bot started successfully")
        logger.info("🔄 Entering main loop (1s cycle)...")
        
        # Start main loop
        await self._main_loop()
    
    async def stop(self):
        """Stop the bot"""
        logger.info("🛑 Stopping LighterBot...")
        
        self.running = False
        
        # Close open position if any
        if self.current_position:
            await self._close_position("Bot shutdown")
        
        # Stop Telegram bot
        if self.telegram_bot:
            await self.telegram_bot.stop_bot()
        
        # Close database
        if self.db_manager:
            await self.db_manager.disconnect()
        
        # Log final statistics
        self._log_final_stats()
        
        logger.info("✅ Bot stopped")
    
    async def _main_loop(self):
        """Main trading loop - runs every 1 second"""
        while self.running:
            try:
                self.loop_count += 1
                
                # Every 5 seconds: Update account state
                if (datetime.now(timezone.utc) - self.last_account_update).total_seconds() >= 5:
                    await self._update_account_state()
                
                # Every 60 minutes: Check ML training (V1→V2 transition)
                if (datetime.now(timezone.utc) - self.last_ml_check).total_seconds() >= 3600:
                    await self._check_ml_training()
                
                # Main trading logic
                await self._trading_cycle()
                
                # Sleep 1 second
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                get_error_handler().handle_error(e, {'loop_count': self.loop_count})
                await asyncio.sleep(5)  # Longer sleep on error
    
    async def _trading_cycle(self):
        """Execute one trading cycle"""
        # Check if we have an open position
        if self.current_position:
            # Monitor position for exit conditions
            await self._monitor_position()
        else:
            # Generate and evaluate new signals
            await self._evaluate_entry()
    
    async def _update_account_state(self):
        """Update account state and check risk conditions"""
        try:
            # Get account state
            self.account_state = await self.lighter_client.get_account_state()
            current_equity = Decimal(str(self.account_state.get('account_value', 0)))
            
            # Check risk state (pass position status to avoid margin-in-use false triggers)
            has_open_positions = self.current_position is not None
            can_trade, reason = self.risk_manager.check_risk_state(current_equity, has_open_positions)
            
            if not can_trade:
                logger.warning(f"⚠️  Trading blocked: {reason}")
                
                # Close position if kill switch triggered
                if self.risk_manager.kill_switch.is_triggered() and self.current_position:
                    await self._close_position("Kill switch triggered")
            
            self.last_account_update = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"❌ Error updating account state: {e}")
    
    async def _check_ml_training(self):
        """Check if ML training should run (V1→V2 transition)"""
        try:
            if self.auto_trainer:
                result = await self.auto_trainer.check_and_train()
                
                if result:
                    logger.info(f"🎓 ML Training completed: {result}")
                    self.trading_logger.log_ml_training(
                        trade_count=result['trade_count'],
                        accuracy=result['accuracy'],
                        phase=result['phase']
                    )
            
            self.last_ml_check = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"❌ Error checking ML training: {e}")
    
    async def _evaluate_entry(self):
        """Evaluate entry signals"""
        try:
            # Double-check no position exists (prevent race conditions)
            if self.current_position:
                return
            
            # Get market data
            market_data = await self._get_market_data()
            
            if not market_data:
                return
            
            # Generate signal from strategies
            signal = await self.strategy_manager.generate_signal(market_data, self.account_state)
            
            if not signal:
                return
            
            self.stats['signals_generated'] += 1
            
            # Log signal
            self.trading_logger.log_trade_signal(
                strategy=signal.get('strategy', 'unknown'),
                symbol=signal.get('symbol', self.symbol),
                signal_type=signal.get('side', 'unknown'),
                strength=signal.get('confidence', 5),
                indicators=market_data.get('indicators', {})
            )
            
            # Validate signal with risk manager
            is_valid, reason = self.risk_manager.validate_signal(signal, self.account_state)
            
            if not is_valid:
                self.stats['signals_rejected'] += 1
                logger.warning(f"⚠️  Signal rejected: {reason}")
                return
            
            self.stats['signals_accepted'] += 1
            
            # CRITICAL: Strict position limit check - ONLY 1 position at a time
            if self.current_position:
                logger.warning("⚠️  Position already exists - STRICT LIMIT: Only 1 position allowed")
                return
            
            # Check cooldown after last position close (prevents rapid re-entry)
            if self.last_position_close_time:
                time_since_close = (datetime.now(timezone.utc) - self.last_position_close_time).total_seconds()
                if time_since_close < self.position_cooldown_seconds:
                    logger.info(f"⏳ Position cooldown active: {self.position_cooldown_seconds - time_since_close:.0f}s remaining")
                    logger.debug(f"   Last position closed at: {self.last_position_close_time}")
                    return
            
            # Execute entry
            await self._execute_entry(signal)
            
        except Exception as e:
            logger.error(f"❌ Error evaluating entry: {e}")
    
    async def _execute_entry(self, signal: Dict[str, Any]):
        """Execute entry order with V2 native OCO and optional trailing stops"""
        # Acquire lock to prevent race condition
        async with self.position_lock:
            # Double-check no position exists after acquiring lock
            if self.current_position:
                logger.warning("⚠️  Position already exists (race condition prevented)")
                return
            
            try:
                symbol = signal['symbol']
                side = signal['side']
                entry_price = Decimal(str(signal['entry_price']))
                size = Decimal(str(signal['size']))
                leverage = signal['leverage']
                sl_price = Decimal(str(signal['sl_price']))
                tp_price = Decimal(str(signal['tp_price']))
                
                logger.info(f"🎯 Executing entry: {side.upper()} {symbol}")
                logger.info(f"   Price: ${entry_price} | Size: {size} | Leverage: {leverage}x")
                logger.info(f"   SL: ${sl_price} | TP: ${tp_price}")
                
                # Place OCO order using V2 native SDK (TRUE exchange-level OCO)
                tx_hash = await self.order_manager.place_oco_order_native(
                    symbol=symbol,
                    side=side,
                    size=size,
                    entry_price=entry_price,
                    sl_price=sl_price,
                    tp_price=tp_price
                )
                
                if tx_hash:
                    logger.info(f"✅ OCO order placed: {tx_hash}")
                    
                    # Wait for order fill confirmation
                    await asyncio.sleep(2)
                    
                    # Get active orders to find SL order ID (V2 doesn't need symbol param)
                    orders = await self.order_manager.get_active_orders()
                    sl_order = next((o for o in orders if o.get('order_type') == 'stop_loss'), None)
                    
                    # Create position record
                    position_id = f"pos_{int(datetime.now(timezone.utc).timestamp())}"
                    self.current_position = {
                        'position_id': position_id,
                        'symbol': symbol,
                        'side': side,
                        'entry_price': float(entry_price),
                        'size': float(size),
                        'leverage': leverage,
                        'sl_price': float(sl_price),
                        'tp_price': float(tp_price),
                        'sl_order_id': sl_order['order_id'] if sl_order else None,
                        'tx_hash': tx_hash,
                        'strategy': signal['strategy'],
                        'entry_time': datetime.now(timezone.utc).isoformat(),
                        'signal': signal
                    }
                    
                    self.stats['positions_opened'] += 1
                    self.risk_manager.on_position_opened(self.current_position)
                    
                    # Enable trailing stop if configured
                    trailing_enabled = os.getenv('TRAILING_SL_ENABLED', 'false').lower() == 'true'
                    if trailing_enabled and sl_order:
                        activation_profit = Decimal(os.getenv('TRAILING_SL_ACTIVATION', '7.0'))
                        trail_level = Decimal(os.getenv('TRAILING_SL_LEVEL', '3.0'))
                        trail_percent = activation_profit - trail_level  # e.g., 7% - 3% = 4% trail distance
                        callback_distance = Decimal('0.5')  # 0.5% minimum move before updating
                        
                        position_size_base = int(size * Decimal('10000000'))  # Convert to base units
                        
                        await self.trailing_manager.enable_trailing_stop(
                            position_id=position_id,
                            market_index=self.market_id,
                            sl_order_index=sl_order['order_id'],
                            position_side=side,
                            entry_price=entry_price,
                            current_sl_price=sl_price,
                            position_size=position_size_base,
                            trail_percent=trail_percent,
                            callback_distance=callback_distance,
                            activation_profit=activation_profit
                        )
                        logger.info(f"🔄 Trailing SL enabled: activate at +{activation_profit}% PnL, trail to +{trail_level}% (distance: {trail_percent}%)")
                    
                    # Enable trailing take profit if configured
                    tp_trailing_enabled = os.getenv('TRAILING_TP_ENABLED', 'false').lower() == 'true'
                    if tp_trailing_enabled and tp_order:
                        tp_activation = Decimal(os.getenv('TRAILING_TP_ACTIVATION', '10.0'))
                        tp_level = Decimal(os.getenv('TRAILING_TP_LEVEL', '12.0'))
                        logger.info(f"🎯 Trailing TP configured: activate at +{tp_activation}% PnL, lock at +{tp_level}% PnL")
                        # Store TP trailing config in position
                        self.current_position['tp_trailing'] = {
                            'enabled': True,
                            'activation': float(tp_activation),
                            'level': float(tp_level),
                            'activated': False
                        }
                    
                    # Save trade entry to database
                    if self.db_manager:
                        trade_data = {
                            'trade_id': position_id,
                            'symbol': symbol,
                            'strategy': signal.get('strategy', 'unknown'),
                            'side': side,
                            'entry_price': float(entry_price),
                            'size': float(size),
                            'leverage': leverage,
                            'entry_time': datetime.now(timezone.utc).isoformat(),
                            'indicators': signal.get('indicators', {}),
                            'ml_prediction': signal.get('ml_prediction'),
                            'ml_confidence': signal.get('ml_confidence')
                        }
                        await self.db_manager.insert_trade(trade_data)
                    
                    logger.info(f"✅ Position opened successfully with TRUE OCO")
                    
            except Exception as e:
                logger.error(f"❌ Error executing entry: {e}")
    
    async def _monitor_position(self):
        """Monitor open position and update trailing stops with live prices"""
        try:
            if not self.current_position:
                return
            
            # Get current market data
            market_data = await self._get_market_data()
            if not market_data:
                return
            
            current_price = Decimal(str(market_data['mark_price']))
            position_id = self.current_position.get('position_id')
            
            # Calculate and log current PnL
            entry_price = Decimal(str(self.current_position.get('entry_price', 0)))
            side = self.current_position.get('side', 'buy')
            leverage = self.current_position.get('leverage', 1)
            
            if entry_price == 0:
                return
            
            # Calculate current PnL %
            if side == 'buy':
                price_change_pct = ((current_price - entry_price) / entry_price) * 100
            else:
                price_change_pct = ((entry_price - current_price) / entry_price) * 100
            
            pnl_pct = price_change_pct * Decimal(str(leverage))
            
            # Update trailing stop manager with current price
            trailing_enabled = os.getenv('TRAILING_SL_ENABLED', 'false').lower() == 'true'
            if trailing_enabled and position_id:
                new_sl = await self.trailing_manager.update_price(position_id, current_price)
                
                if new_sl:
                    logger.info(f"🔄 Trailing SL updated to ${new_sl}")
                    self.current_position['sl_price'] = float(new_sl)
            
            # Update trailing take profit if configured
            tp_trailing_config = self.current_position.get('tp_trailing')
            if tp_trailing_config and tp_trailing_config.get('enabled'):
                await self._update_trailing_tp(current_price, pnl_pct, tp_trailing_config)
            
            # Check if position was closed (check both symbol match and non-zero size)
            positions = await self.lighter_client.get_positions()
            position_exists = any(
                p.get('symbol') == self.current_position['symbol'] and abs(float(p.get('size', 0))) > 0.001
                for p in positions
            )
            
            if not position_exists:
                # Position was closed (SL or TP hit)
                logger.info(f"🔔 Position closed detected for {self.current_position['symbol']}")
                await self._on_position_closed()
            
        except Exception as e:
            logger.error(f"❌ Error monitoring position: {e}")
    
    async def _update_trailing_tp(self, current_price: Decimal, pnl_pct: Decimal, tp_config: dict):
        """
        Update trailing take profit - closes position when profit reaches target level
        
        Logic:
        1. Wait until PnL reaches activation threshold (e.g., +10%)
        2. Once activated, if PnL drops below target level (e.g., +12%), close position
        3. This locks in profit when price starts to reverse after hitting target
        """
        try:
            activation = Decimal(str(tp_config['activation']))
            level = Decimal(str(tp_config['level']))
            activated = tp_config.get('activated', False)
            
            # Activate trailing TP when profit reaches activation threshold
            if not activated and pnl_pct >= activation:
                tp_config['activated'] = True
                tp_config['peak_pnl'] = float(pnl_pct)
                logger.info(f"🎯 Trailing TP activated at +{pnl_pct:.2f}% PnL (activation: +{activation}%)")
                return
            
            # If activated, track peak PnL
            if activated:
                peak_pnl = Decimal(str(tp_config.get('peak_pnl', activation)))
                
                # Update peak if current PnL is higher
                if pnl_pct > peak_pnl:
                    tp_config['peak_pnl'] = float(pnl_pct)
                    logger.info(f"📈 Trailing TP: New peak +{pnl_pct:.2f}% PnL")
                    return
                
                # Close position if PnL drops below target level
                if pnl_pct < level:
                    logger.info(f"🎯 Trailing TP triggered: PnL dropped to +{pnl_pct:.2f}% (target: +{level}%, peak: +{peak_pnl:.2f}%)")
                    logger.info(f"💰 Closing position to lock in profit...")
                    
                    # Close position via market order
                    symbol = self.current_position['symbol']
                    side = self.current_position['side']
                    size = Decimal(str(self.current_position['size']))
                    
                    # Reverse side for close
                    close_side = 'sell' if side == 'buy' else 'buy'
                    
                    # Place market order to close
                    await self.order_manager.place_market_order(
                        symbol=symbol,
                        side=close_side,
                        size=size
                    )
                    
                    logger.info(f"✅ Trailing TP: Position closed at +{pnl_pct:.2f}% PnL")
                    
        except Exception as e:
            logger.error(f"❌ Error updating trailing TP: {e}")
    
    async def _on_position_closed(self):
        """Handle position closed event and disable trailing stops"""
        try:
            if not self.current_position:
                return
            
            # Check if position was open long enough (prevent instant close bug)
            entry_time_str = self.current_position.get('entry_time')
            if entry_time_str:
                entry_time = datetime.fromisoformat(entry_time_str)
                position_duration = (datetime.now(timezone.utc) - entry_time).total_seconds()
                
                if position_duration < self.min_position_duration:
                    logger.warning(f"⚠️  Position closed too quickly ({position_duration:.0f}s) - possible exchange bug")
                    logger.warning(f"   Increasing cooldown to 5 minutes to prevent rapid open-close loop")
                    # Don't clear position immediately, let it be handled on next cycle
                    self.last_position_close_time = datetime.now(timezone.utc)
                    self.current_position = None
                    return
            
            symbol = self.current_position['symbol']
            position_id = self.current_position.get('position_id')
            entry_price = Decimal(str(self.current_position.get('entry_price', 0)))
            size = Decimal(str(self.current_position.get('size', 0)))
            side = self.current_position.get('side', 'buy')
            
            # Disable trailing stop
            if position_id and self.trailing_manager:
                self.trailing_manager.disable_trailing_stop(position_id)
            
            
            # Get current position data from exchange for actual PnL
            positions = await self.lighter_client.get_positions()
            actual_pnl = Decimal('0')
            exit_price = Decimal('0')
            
            for pos in positions:
                if pos['symbol'] == symbol and abs(float(pos['size'])) > 0:
                    actual_pnl = Decimal(str(pos.get('unrealized_pnl', 0)))
                    exit_price = Decimal(str(pos.get('mark_price', entry_price)))
                    break
            
            # Calculate PnL percentage
            pnl_pct = Decimal('0')
            if entry_price > 0 and size > 0:
                pnl_pct = (actual_pnl / (entry_price * size)) * Decimal('100')
            
            logger.info(f"📊 Position closed: {symbol}")
            logger.info(f"   Entry: ${entry_price:.2f} | Size: {size}")
            logger.info(f"   PnL: ${actual_pnl:.2f}")
            
            # Update risk manager
            self.risk_manager.on_position_closed(symbol, actual_pnl)
            
            # Log position closed to console
            self.trading_logger.log_position_closed(
                symbol=symbol,
                side=side,
                size=size,
                exit_price=exit_price,
                pnl=actual_pnl,
                pnl_pct=pnl_pct
            )
            
            # Save trade exit to database
            if self.db_manager:
                exit_data = {
                    'exit_price': float(exit_price),
                    'exit_time': datetime.now(timezone.utc).isoformat(),
                    'pnl_usd': float(actual_pnl),
                    'pnl_pct': float(pnl_pct),
                    'fees_usd': 0.0,  # Fees not available from exchange API
                    'duration_seconds': int((datetime.now(timezone.utc) - datetime.fromisoformat(self.current_position.get('entry_time'))).total_seconds()) if self.current_position.get('entry_time') else 0,
                    'exit_reason': 'OCO filled'
                }
                trade_id = self.current_position.get('position_id')
                await self.db_manager.update_trade_exit(trade_id, exit_data)
            
            self.stats['positions_closed'] += 1
            self.current_position = None
            self.last_position_close_time = datetime.now(timezone.utc)  # Activate cooldown
            
        except Exception as e:
            logger.error(f"❌ Error handling position closed: {e}")
    
    async def _close_position(self, reason: str):
        """Manually close position and disable trailing stops"""
        try:
            if not self.current_position:
                return
            
            symbol = self.current_position['symbol']
            position_id = self.current_position.get('position_id')
            
            logger.info(f"🔴 Closing position: {symbol}")
            logger.info(f"   Reason: {reason}")
            
            # Disable trailing stop if active
            if position_id and self.trailing_manager:
                self.trailing_manager.disable_trailing_stop(position_id)
                logger.info(f"   Trailing stop disabled")
            
            # Close position via exchange
            await self.lighter_client.close_position(symbol)
            
            # Cancel OCO orders (V2 method)
            await self.order_manager.cancel_all_orders(symbol)
            
            # Handle closed position
            await self._on_position_closed()
            
        except Exception as e:
            logger.error(f"❌ Error closing position: {e}")
    
    async def _get_market_data(self) -> Optional[Dict[str, Any]]:
        """Get market data with real technical indicators from candlestick data"""
        try:
            from app.indicators.technical_indicators import TechnicalIndicators
            
            # Get real-time orderbook data for current price
            market_data_result = await self.lighter_client.get_market_data(self.symbol, self.market_id)
            
            if not market_data_result or 'last_trade_price' not in market_data_result:
                return None
            
            current_price = float(market_data_result['last_trade_price'])
            volume_24h = float(market_data_result.get('daily_base_token_volume', 0))
            price_change_24h = float(market_data_result.get('daily_price_change', 0))
            
            # Fetch multi-timeframe candlestick data
            multi_tf_candles = await self.lighter_client.get_multi_timeframe_data(self.market_id)
            
            # Use primary timeframe (5m) for indicator calculation
            primary_candles = multi_tf_candles.get('5m', [])
            
            if not primary_candles or len(primary_candles) < 50:
                logger.warning("⚠️  Insufficient candlestick data, using fallback indicators")
                # Fallback to simplified indicators
                price_change_pct = price_change_24h / current_price if current_price > 0 else 0
                return {
                    'symbol': self.symbol,
                    'mark_price': current_price,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'volume_24h': volume_24h,
                    'price_change_24h': price_change_24h,
                    'indicators': {
                        'rsi': 50 + (price_change_pct * 500),
                        'ema_fast': current_price * 1.01,
                        'ema_slow': current_price * 0.99,
                        'macd': {'histogram': price_change_pct * 10},
                        'adx': min(100, abs(price_change_pct) * 1000),
                        'volume_ratio': 1.2,
                        'price_change_5m': price_change_pct * 0.05,
                        'price_change_1h': price_change_pct * 0.20,
                        'bb_position': 0.5
                    }
                }
            
            # Calculate real technical indicators from candlestick data
            indicator_config = {
                'rsi_period': int(os.getenv('RSI_PERIOD', '14')),
                'ema_fast': int(os.getenv('EMA_FAST', '21')),
                'ema_slow': int(os.getenv('EMA_SLOW', '50')),
                'macd_fast': int(os.getenv('MACD_FAST', '12')),
                'macd_slow': int(os.getenv('MACD_SLOW', '26')),
                'macd_signal': int(os.getenv('MACD_SIGNAL', '9')),
                'adx_period': int(os.getenv('ADX_PERIOD', '14')),
                'bb_period': int(os.getenv('BB_PERIOD', '20'))
            }
            
            indicators = TechnicalIndicators.calculate_all_indicators(primary_candles, indicator_config)
            
            # Add multi-timeframe confirmation
            # Check trend alignment across timeframes
            tf_alignment = self._check_multi_tf_alignment(multi_tf_candles, indicator_config)
            indicators['multi_tf_aligned'] = tf_alignment
            
            market_data = {
                'symbol': self.symbol,
                'mark_price': current_price,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'volume_24h': volume_24h,
                'price_change_24h': price_change_24h,
                'indicators': indicators,
                'candles': {
                    '5m': primary_candles[-20:],  # Last 20 candles for reference
                    '1h': multi_tf_candles.get('1h', [])[-10:] if '1h' in multi_tf_candles else []
                }
            }
            
            return market_data
            
        except Exception as e:
            logger.error(f"❌ Error getting market data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _check_multi_tf_alignment(self, multi_tf_candles: Dict[str, List[Dict[str, Any]]], 
                                   config: Dict[str, int]) -> bool:
        """
        Check if trends are aligned across multiple timeframes
        
        Args:
            multi_tf_candles: Multi-timeframe candlestick data
            config: Indicator configuration
            
        Returns:
            True if trends aligned, False otherwise
        """
        try:
            from app.indicators.technical_indicators import TechnicalIndicators
            
            alignments = []
            
            for tf in ['5m', '15m', '1h']:
                if tf not in multi_tf_candles or len(multi_tf_candles[tf]) < 50:
                    continue
                
                candles = multi_tf_candles[tf]
                closes = [c['close'] for c in candles]
                
                ema_fast = TechnicalIndicators.calculate_ema(closes, config.get('ema_fast', 21))
                ema_slow = TechnicalIndicators.calculate_ema(closes, config.get('ema_slow', 50))
                
                # Bullish if fast > slow, bearish if fast < slow
                trend = 1 if ema_fast > ema_slow else -1
                alignments.append(trend)
            
            if not alignments:
                return False
            
            # All trends must be in same direction
            return all(t == alignments[0] for t in alignments)
            
        except Exception as e:
            logger.error(f"❌ Error checking multi-TF alignment: {e}")
            return False
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"🛑 Received signal {signum}, initiating shutdown...")
        self.running = False
    
    def _log_final_stats(self):
        """Log final statistics"""
        runtime = (datetime.now(timezone.utc) - self.stats['start_time']).total_seconds()
        
        logger.info("=" * 60)
        logger.info("📊 FINAL STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Runtime: {runtime/3600:.2f} hours")
        logger.info(f"Loop cycles: {self.loop_count}")
        logger.info(f"Signals generated: {self.stats['signals_generated']}")
        logger.info(f"Signals accepted: {self.stats['signals_accepted']}")
        logger.info(f"Signals rejected: {self.stats['signals_rejected']}")
        logger.info(f"Positions opened: {self.stats['positions_opened']}")
        logger.info(f"Positions closed: {self.stats['positions_closed']}")
        logger.info("=" * 60)


async def main():
    """Main entry point"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("🤖 LighterBot v1.0")
    logger.info("🔗 Lighter Protocol DEX Trading Bot")
    logger.info("=" * 60)
    
    # Create and start bot
    bot = LighterBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        get_error_handler().handle_error(e, {'context': 'main'})
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
