"""
Advanced Trading Bot with Multiple Strategies + Institutional Features
"""
import asyncio
import signal
import sys
from typing import Optional, List
from datetime import datetime, timedelta
from asyncio import Lock
from config import settings
from market_data import MarketData
from order_manager import OrderManager
from risk_manager import AdvancedRiskManager, Position
from strategies import (
    StrategyManager, MomentumStrategy, MeanReversionStrategy,
    OrderFlowStrategy, CandlestickStrategy, MarketDataWrapper,
    Signal, SignalType
)
from logger import get_logger, get_alert_manager
from lighter_client import close_client, get_client
from utils import resolve_market_metadata, market_metadata
from indicators import TechnicalIndicators
from metrics import bot_metrics
from win_rate_tracker import win_rate_tracker

# INSTITUTIONAL FEATURES
from strategy_performance import strategy_tracker
from drawdown_protection import drawdown_protection
from time_filter import is_trading_hours, get_trading_session
from multi_timeframe import mtf_analyzer
from institutional_pipeline import institutional_pipeline
from hybrid_exit_manager import get_hybrid_exit_manager
from indicators import TechnicalIndicators
from metrics import bot_metrics
from win_rate_tracker import win_rate_tracker
from vwap_filter import vwap_filter  # Institution-grade entry filter


class AdvancedTradingBot:
    """
    Advanced Trading Bot with Multiple Strategies
    
    Features:
    - Multiple concurrent trading strategies (technical + order flow + sentiment)
    - Advanced risk management with Kelly Criterion
    - Auto stop-loss and take-profit
    - Real-time position monitoring
    - Performance tracking
    """
    
    def __init__(self):
        self.logger = get_logger()
        self.alert_manager = get_alert_manager()
        
        # Initialize components
        self.logger.info("Initializing Advanced Trading Bot...")
        
        # Lock to prevent concurrent position openings
        self.position_opening_lock = Lock()
        
        self.market_data = MarketData()
        self.order_manager = OrderManager()
        self.risk_manager = AdvancedRiskManager(self.order_manager, self.market_data)
        
        # Hybrid exit manager for OCO + Bot management
        self.hybrid_exit_manager = get_hybrid_exit_manager(self.order_manager)
        
        # Start Prometheus metrics server
        bot_metrics.start_server()
        bot_metrics.set_bot_info({
            "version": "2.0",
            "market": settings.trading_symbol,
            "environment": settings.environment
        })
        
        # Initialize strategy manager with ALL institutional strategies
        self.strategy_manager = StrategyManager()
        
        # MULTI-STRATEGY CONSENSUS for "no loss" trading
        if settings.enable_momentum_strategy:
            self.strategy_manager.add_strategy(MomentumStrategy())
            self.logger.info("✓ Momentum Strategy (trend following)")
        
        if settings.enable_mean_reversion_strategy:
            self.strategy_manager.add_strategy(MeanReversionStrategy())
            self.logger.info("✓ Mean Reversion Strategy (oversold/overbought)")
        
        if settings.enable_orderflow_strategy:
            self.strategy_manager.add_strategy(OrderFlowStrategy())
            self.logger.info("✓ Order Flow Strategy (institutional money flow)")
        
        # Always enable Candlestick (pattern confirmation)
        self.strategy_manager.add_strategy(CandlestickStrategy())
        self.logger.info("✓ Candlestick Strategy (pattern recognition)")
        
        self.logger.info(f"📊 MULTI-STRATEGY MODE: {len(self.strategy_manager.strategies)} strategies for maximum accuracy")
        
        # Bot state
        self.running = False
        self.last_risk_check = datetime.now() - timedelta(seconds=35)  # Ensure immediate first check
        self.last_strategy_run = datetime.now()
        
        # ADAPTIVE MONITORING: 1s when positions open (fast TP/SL), 5s when idle
        self.has_open_positions = False
        self.position_cache = []
        self.last_position_fetch = datetime.now() - timedelta(seconds=100)
        
        # TRAILING STOP: Track highest PnL for each position (institutions protect profits)
        self.position_highest_pnl = {}  # {position_id: highest_pnl_pct}
        
        # SMART REJECTION: Track failed trades to avoid repeating mistakes
        self.recent_losses = []  # Track last 5 losing trades
        self.last_loss_time = None
        self.consecutive_losses = 0
        
        # Track recently closed positions to avoid duplicate closes
        self.recently_closed_positions: set = set()
        
        # Price history for technical analysis
        self.price_history = []
        self.high_history = []
        self.low_history = []
        self.volume_history = []
        self.max_history_len = 100
        
        # Performance tracking
        self.start_time = datetime.now()
        self.trade_count = 0
        self.total_pnl = 0.0
        
        self.logger.info("Advanced Trading Bot initialized with {} strategies".format(
            len(self.strategy_manager.strategies)
        ))
    
    async def update_market_data_history(self):
        """Update price history for technical analysis"""
        try:
            # Get current market data
            mid_price = await self.market_data.get_mid_price()
            best_bid, best_ask = await self.market_data.get_best_bid_ask()
            
            # For simplicity, use mid price as high/low/close
            # In production, fetch actual OHLCV data
            self.price_history.append(mid_price)
            self.high_history.append(best_ask)
            self.low_history.append(best_bid)
            self.volume_history.append(0)  # Volume would come from exchange
            
            # Update VWAP filter for institution-grade entries
            vwap_filter.update_vwap(mid_price, 1.0)  # Use placeholder volume
            
            # Feed data to ML predictor
            try:
                from ml_predictor import ml_predictor
                ml_predictor.add_candle(
                    open_price=mid_price,
                    high=best_ask,
                    low=best_bid,
                    close=mid_price,
                    volume=1.0  # Placeholder
                )
            except Exception as e:
                self.logger.debug(f"ML predictor update failed: {e}")
            
            # Keep only recent history
            if len(self.price_history) > self.max_history_len:
                self.price_history = self.price_history[-self.max_history_len:]
                self.high_history = self.high_history[-self.max_history_len:]
                self.low_history = self.low_history[-self.max_history_len:]
                self.volume_history = self.volume_history[-self.max_history_len:]
        
        except Exception as e:
            self.logger.error(f"Error updating market data: {e}")
    
    async def execute_signal(self, signal: Signal) -> bool:
        """
        Execute a trading signal with INSTITUTIONAL FILTERS
        
        Args:
            signal: Trading signal from strategy
            
        Returns:
            True if order was executed
        """
        try:
            # INSTITUTION TRICK #5: Don't trade after 2+ consecutive losses (wait for calm)
            if self.consecutive_losses >= 2:
                time_since_loss = (datetime.now() - self.last_loss_time).total_seconds() if self.last_loss_time else 999
                if time_since_loss < 180:  # Wait 3 minutes after 2 losses
                    self.logger.warning(f"⏸️ PAUSE: {self.consecutive_losses} consecutive losses. Waiting {180-time_since_loss:.0f}s before next trade")
                    return False
            
            # ========================================
            # VWAP ENTRY FILTER (Institution Grade)
            # ========================================
            signal_direction = "long" if signal.signal_type == SignalType.BUY else "short"
            approved, reason = vwap_filter.should_enter_trade(signal.price, signal_direction)
            if not approved:
                self.logger.warning(f"🚫 VWAP Filter: {reason}")
                return False
            
            # ========================================
            # INSTITUTIONAL FILTER PIPELINE
            # ========================================
            approved, reason, adjustments = await institutional_pipeline.should_execute_trade(
                signal=signal,
                market_data=self.market_data
            )
            
            if not approved:
                self.logger.info(f"Trade rejected: {reason}")
                return False
            
            # Apply confidence boost from multi-timeframe
            original_strength = signal.strength
            signal.strength = min(1.0, signal.strength + adjustments['confidence_boost'])
            
            if adjustments['confidence_boost'] > 0:
                self.logger.info(
                    f"📊 Multi-TF boost: {original_strength:.2f} → {signal.strength:.2f}"
                )
            
            # Calculate stop-loss price using settings
            stop_loss_pct = settings.stop_loss_percent / 100.0  # Convert percentage to decimal
            if signal.signal_type == SignalType.BUY:
                stop_loss_price = signal.price * (1 - stop_loss_pct)
            else:
                stop_loss_price = signal.price * (1 + stop_loss_pct)
            
            # Risk check with position sizing (risk manager calculates size based on account balance)
            # Pass 0.0 as initial size so risk manager calculates optimal size
            approved, reason, adjusted_size = await self.risk_manager.check_order_risk(
                side="buy" if signal.signal_type == SignalType.BUY else "sell",
                size=0.0,  # Let risk manager calculate size based on position_size_percent
                price=signal.price,
                market_id=self.market_data.market_id,  # Use current market_id from market_data
                stop_loss=stop_loss_price
            )
            
            if not approved:
                self.logger.warning(f"Order rejected by risk manager: {reason}")
                return False
            
            # Apply drawdown protection size multiplier
            adjusted_size = adjusted_size * adjustments['size_multiplier']
            
            if adjustments['size_multiplier'] < 1.0:
                self.logger.warning(
                    f"⚠️ Size reduced to {adjustments['size_multiplier']*100:.0f}%: {adjusted_size:.4f}"
                )
            
            # Place order WITH HYBRID OCO PROTECTION
            side = "buy" if signal.signal_type == SignalType.BUY else "sell"
            
            # ========================================
            # HYBRID OCO STRATEGY (Exchange + Bot)
            # ========================================
            # Exchange handles basic TP/SL (instant, 0ms, survives crashes)
            # Bot can intervene for trailing stops and early exits
            
            # 🔒 LOCK to prevent concurrent position openings (max 3 positions)
            async with self.position_opening_lock:
                self.logger.info(f"🔒 Acquired position opening lock")
                
                # Re-check position count inside lock using LOCAL count (no API lag)
                current_position_count = len(self.order_manager.local_positions)
                
                if current_position_count >= settings.max_open_positions:
                    self.logger.warning(f"🛑 STRICT LIMIT: Already have {current_position_count}/{settings.max_open_positions} positions - BLOCKED")
                    return False
                
                self.logger.info(f"✅ Position check: {current_position_count}/{settings.max_open_positions} - proceeding")
                self.logger.info(f"Executing {side.upper()} order: size={adjusted_size:.4f} @ ${signal.price:.2f}")
                self.logger.info(f"Reason: {signal.reason}")
                
                success, oco_info = await self.order_manager.place_position_with_oco(
                    side=side,
                    size=adjusted_size,
                    entry_price=signal.price,
                    tp_pct=2.0,  # +2% TP
                    sl_pct=2.0,  # -2% SL
                    market_id=self.market_data.market_id
                )
                
                if not success:
                    self.logger.error(f"Failed to execute trade")
                    return False
                
                if oco_info:
                    self.logger.info(f"🎯 Position opened with OCO protection")
                    self.logger.info(f"   TP @ ${oco_info['tp_price']:.2f} (+2%) - Exchange managed")
                    self.logger.info(f"   SL @ ${oco_info['sl_price']:.2f} (-2%) - Exchange managed")
                    self.logger.info(f"   Bot monitors for trailing/early exit opportunities")
                else:
                    self.logger.warning(f"⚠️ Position opened WITHOUT OCO - Bot managing all exits")
                
                # Update position tracking
                self.has_open_positions = True
                
                order = True  # Success flag for downstream logic
            
            if order:
                self.trade_count += 1
                
                # Set flag for ADAPTIVE MONITORING: 1-second checks when positions open
                self.has_open_positions = True
                
                # REGISTER TRADE for early exit detection
                try:
                    direction = 'long' if side == 'buy' else 'short'
                    trade_id = f"{settings.trading_symbol}_{self.trade_count}"
                    
                    self.risk_manager.trade_validator.register_trade(
                        trade_id=trade_id,
                        entry_price=signal.price,
                        direction=direction,
                        reason=signal.reason,
                        confidence=signal.strength,
                        market_data=None  # Will fetch during monitoring
                    )
                    self.logger.info(f"📋 Trade registered for early exit detection: {trade_id}")
                except Exception as e:
                    self.logger.error(f"Error registering trade: {e}")
                
                # Record metrics
                bot_metrics.record_trade(
                    side=side,
                    strategy=signal.reason.split(':')[0] if ':' in signal.reason else "unknown",
                    market=settings.trading_symbol
                )
                
                self.alert_manager.send_alert(
                    f"Order executed: {side.upper()} {adjusted_size:.4f} @ ${signal.price:.2f}",
                    "INFO"
                )
                return True
            
            return False
        
        except Exception as e:
            self.logger.error(f"Error executing signal: {e}")
            return False
    
    async def run_strategies(self):
        """
        🎯 MULTI-MODE TRADING STRATEGY EXECUTION
        =======================================
        
        Supports three modes:
        1. MULTI-TOP-3: Focus on ETH/BTC/SOL for 2% quick exits
        2. SINGLE-MARKET: Traditional single token trading
        """
        try:
            # MODE 1: TOP 3 HIGH-VOLUME (2% QUICK EXIT)
            if settings.trading_symbol == "MULTI-TOP-3":
                await self._run_top3_strategy()
            
            # MODE 2: SINGLE-MARKET
            else:
                await self._run_single_market_strategy()
        
        except Exception as e:
            self.logger.error(f"Error in strategy execution: {e}", exc_info=True)
    
    async def _run_top3_strategy(self):
        """
        🎯 TOP 3 HIGH-VOLUME 2% QUICK EXIT STRATEGY
        ==========================================
        
        Focus: ETH-PERP, BTC-PERP, SOL-PERP
        Goal: 50 trades × 2% = 100% profit
        """
        try:
            self.logger.info("🎯 TOP 3 HIGH-VOLUME SCANNER (2% QUICK EXIT)")
            self.logger.info("="*70)
            
            # Get current positions
            positions = await self.order_manager.get_positions()
            open_positions = [pos for pos in positions if pos.is_open]
            
            # Get account info
            account_info = await self.order_manager.get_account_info()
            if isinstance(account_info, dict):
                if 'accounts' in account_info and len(account_info['accounts']) > 0:
                    balance = float(account_info['accounts'][0].get('collateral', 0))
                else:
                    balance = float(account_info.get('collateral', 0))
            else:
                balance = 0.0
            
            # Calculate portfolio heat
            portfolio_heat = await self.risk_manager.calculate_portfolio_heat()
            
            self.logger.info(f"💰 Available Capital: ${balance:.2f}")
            self.logger.info(f"📊 Portfolio Heat: {portfolio_heat:.1%}")
            self.logger.info(f"🎯 Open Positions: {len(open_positions)}/3")
            self.logger.info("="*70)
            
            # Scan top 3 tokens for opportunities
            self.logger.info("🔍 SCANNING ETH, BTC, SOL FOR 2% OPPORTUNITIES...")
            all_opportunities = await top3_scanner.scan_for_opportunities()
            
            if not all_opportunities:
                self.logger.info("⏳ NO 2% QUICK EXIT SETUPS - WAITING FOR QUALITY SIGNALS")
                self.logger.info(f"   Trading top 3: ETH-PERP, BTC-PERP, SOL-PERP")
                return
            
            # Find first opportunity that we don't already have a position in
            best_opportunity = None
            for opp in all_opportunities:
                existing_pos = next((pos for pos in open_positions if pos.market_id == opp.market_id), None)
                if not existing_pos:
                    best_opportunity = opp
                    break
            
            if not best_opportunity:
                self.logger.info(f"⏸️  Already in all available opportunities - monitoring {len(open_positions)} positions")
                return
            
            # Check if we can open a new position (max 5)
            if len(open_positions) >= settings.max_open_positions:
                self.logger.info(f"⏸️  Max positions reached ({len(open_positions)}/{settings.max_open_positions}) - waiting for exits")
                return
            
            # Display opportunity
            self.logger.info(f"")
            self.logger.info(f"🎯 BEST 2% OPPORTUNITY FOUND!")
            self.logger.info(f"="*70)
            self.logger.info(f"   Token: {best_opportunity.symbol}")
            self.logger.info(f"   Direction: {best_opportunity.direction}")
            self.logger.info(f"   Entry: ${best_opportunity.entry_price:.2f}")
            # With 5x leverage, 2% PnL = 0.4% price move (2% / 5 = 0.4%)
            price_move_pct = settings.profit_level_1_percent / settings.leverage / 100
            target_price = best_opportunity.entry_price * (1 + price_move_pct if best_opportunity.direction == "LONG" else 1 - price_move_pct)
            self.logger.info(f"   Target: +{settings.profit_level_1_percent}% PnL = ${target_price:.2f} ({price_move_pct*100:.2f}% price move with {settings.leverage}x leverage)")
            stop_price = best_opportunity.entry_price * (1 - settings.stop_loss_percent/settings.leverage/100 if best_opportunity.direction == "LONG" else 1 + settings.stop_loss_percent/settings.leverage/100)
            self.logger.info(f"   Stop: -{settings.stop_loss_percent}% PnL = ${stop_price:.2f}")
            self.logger.info(f"   Quality Score: {best_opportunity.total_score:.2f}")
            self.logger.info(f"   Confidence: {best_opportunity.confidence:.0%}")
            self.logger.info(f"="*70)
            
            # Create signal
            signal = Signal(
                signal_type=SignalType.BUY if best_opportunity.direction == "LONG" else SignalType.SELL,
                strength=best_opportunity.confidence,
                price=best_opportunity.entry_price,
                reason=f"Top3 2% Exit: {best_opportunity.symbol} (Score: {best_opportunity.total_score:.2f})",
                timestamp=datetime.now()
            )
            
            # Set market ID for order execution
            self.market_data.market_id = best_opportunity.market_id
            
            # Execute the trade
            success = await self.execute_signal(signal)
            
            if success:
                self.logger.info(f"✅ 2% QUICK EXIT TRADE EXECUTED ON {best_opportunity.symbol}!")
            else:
                self.logger.info(f"❌ Failed to execute trade on {best_opportunity.symbol}")
        
        except Exception as e:
            self.logger.error(f"Error in top 3 strategy: {e}", exc_info=True)
            self.alert_manager.alert_error(f"Top 3 strategy error: {e}")
    
    async def _run_single_market_strategy(self):
        """Traditional single-market trading strategy"""
        self.logger.info(f"Trading {settings.trading_symbol}...")
        
        # Create wrapper and fetch latest data
        wrapper = MarketDataWrapper(self.market_data)
        await wrapper.fetch_latest_data()
        
        # Check if we have valid price data
        if wrapper.price == 0.0:
            self.logger.warning("No price data available, skipping strategy run")
            return
        
        # Get signals from all strategies (official SDK methods only)
        signals = await self.strategy_manager.analyze_market(wrapper)
        
        if signals:
            # Get consensus from multiple signals
            best_signal = self.strategy_manager.get_consensus_signal(signals)
            if best_signal:
                self.logger.info(f"✅ Signal: {best_signal.signal_type.name} - Strength: {best_signal.strength:.2f} - {best_signal.reason}")
                await self.execute_signal(best_signal)
            else:
                self.logger.debug("No consensus from signals")
        else:
            self.logger.debug("No signals generated")
        
        self.last_strategy_run = datetime.now()
    
    async def check_risk_and_positions_fast(self):
        """
        FAST position monitoring when positions are open (1-second loop)
        Minimal logging, cached positions, prioritizes TP/SL execution
        """
        try:
            # Fetch positions only every 3 seconds to save API calls (still fast enough)
            now = datetime.now()
            if (now - self.last_position_fetch).total_seconds() >= 3:
                self.position_cache = await self.order_manager.get_positions()
                self.last_position_fetch = now
                self.has_open_positions = len([p for p in self.position_cache if p.is_open]) > 0
                
                # Sync local_positions with actual API positions
                actual_count = len([p for p in self.position_cache if p.is_open])
                local_count = len(self.order_manager.local_positions)
                
                if local_count != actual_count:
                    # Only sync if discrepancy persists (allow 10 seconds for API lag)
                    should_sync = False
                    if actual_count == 0 and local_count > 0:
                        # Check if local positions are old (>10s)
                        oldest_time = min(p.get('opened_at', datetime.now()) for p in self.order_manager.local_positions)
                        age_seconds = (now - oldest_time).total_seconds()
                        if age_seconds > 10:
                            self.logger.info(f"🔄 Syncing local positions: {local_count} → {actual_count} (positions closed)")
                            self.order_manager.local_positions.clear()
                            should_sync = True
                    elif actual_count > local_count:
                        # API has more positions than local (shouldn't happen, but sync anyway)
                        self.logger.info(f"🔄 Syncing local positions: {local_count} → {actual_count} (API ahead)")
                        self.order_manager.local_positions.clear()
                        should_sync = True
                    elif actual_count < local_count and (now - self.last_position_fetch).total_seconds() > 15:
                        # API shows fewer but only after 15s (positions really closed)
                        self.logger.info(f"🔄 Syncing local positions: {local_count} → {actual_count} (confirmed closed)")
                        self.order_manager.local_positions = self.order_manager.local_positions[-actual_count:] if actual_count > 0 else []
                        should_sync = True
                
                if self.has_open_positions:
                    self.logger.debug(f"⚡ FAST 1s check: {len([p for p in self.position_cache if p.is_open])} open positions")
            
            # Fast TP/SL check using cached positions
            if self.position_cache:
                # Only log position count if it changed
                current_count = len([p for p in self.position_cache if p.is_open])
                if not hasattr(self, '_last_logged_count') or self._last_logged_count != current_count:
                    self.logger.info(f"🔍 Monitoring {current_count} open positions")
                    self._last_logged_count = current_count
                
                # ========================================
                # PORTFOLIO USAGE CHECK (60% MAX)
                # ========================================
                # Check if portfolio exceeds 60% - close extra positions immediately
                portfolio_heat = await self.risk_manager.calculate_portfolio_heat()
                if portfolio_heat > 0.60:  # 60% max usage
                    self.logger.error(f"🚨 PORTFOLIO OVERHEATED: {portfolio_heat:.1%} > 60%")
                    self.logger.error(f"🛑 CLOSING EXTRA POSITIONS IMMEDIATELY!")
                    
                    # Close positions until we're under 60%
                    # Sort by PnL - close losing positions first
                    sorted_positions = sorted(
                        [p for p in self.position_cache if p.is_open],
                        key=lambda p: p.pnl_percentage
                    )
                    
                    for position in sorted_positions:
                        if portfolio_heat <= 0.60:
                            break
                        
                        position_id = f"{position.market_id}_{position.size}"
                        self.logger.warning(f"🔻 Closing position to reduce usage: {position_id} ({position.pnl_percentage:.2f}%)")
                        
                        # Close immediately
                        success = await self.hybrid_exit_manager.close_position_hybrid(
                            position=position,
                            reason=f"Portfolio overheat: {portfolio_heat:.1%} > 60%",
                            position_id=position_id
                        )
                        
                        if success:
                            self.logger.info(f"✅ Closed position {position_id} to reduce usage")
                            # Recalculate portfolio heat
                            portfolio_heat = await self.risk_manager.calculate_portfolio_heat()
                        else:
                            self.logger.error(f"❌ Failed to close position {position_id}")
                
                for position in self.position_cache:
                    if not position.is_open:
                        continue
                    
                    pnl_pct = position.pnl_percentage
                    symbol = settings.trading_symbol
                    position_id = f"{position.market_id}_{position.size}"
                    
                    # Track highest PnL for trailing stop
                    if position_id not in self.position_highest_pnl:
                        self.position_highest_pnl[position_id] = pnl_pct
                        self.logger.info(f"🎯 NEW: {symbol} @ {pnl_pct:.2f}%")
                    else:
                        if pnl_pct > self.position_highest_pnl[position_id]:
                            old_highest = self.position_highest_pnl[position_id]
                            self.position_highest_pnl[position_id] = pnl_pct
                            self.logger.info(f"📈 {symbol}: {old_highest:.2f}% → {pnl_pct:.2f}%")
                    
                    highest_pnl = self.position_highest_pnl[position_id]
                    
                    # ==================================================
                    # HYBRID EXIT MANAGEMENT: OCO (Exchange) + Bot (Advanced)
                    # ==================================================
                    should_close, reason = await self.hybrid_exit_manager.check_position_for_hybrid_exit(
                        position=position,
                        pnl_pct=pnl_pct,
                        highest_pnl=highest_pnl,
                        position_id=position_id
                    )
                    
                    if should_close:
                        # Check if already closed (avoid duplicates)
                        if position_id in self.hybrid_exit_manager.recently_closed:
                            continue
                        
                        # Close via hybrid manager
                        success = await self.hybrid_exit_manager.close_position_hybrid(
                            position=position,
                            reason=reason,
                            position_id=position_id
                        )
                        
                        if success:
                            # Cleanup tracking
                            self.has_open_positions = False
                            self.position_cache = None
                            self.last_position_fetch = 0
                            
                            # Update win rate
                            if pnl_pct > 0:
                                self.consecutive_losses = 0
                            else:
                                self.consecutive_losses += 1
                            
                            # Cleanup highest PnL tracking
                            if position_id in self.position_highest_pnl:
                                del self.position_highest_pnl[position_id]
                            
                            self.logger.info(f"✅ Position closed via hybrid: {reason}")
                            continue
                        else:
                            self.logger.error(f"❌ Failed to close position: {reason}")
                            continue
            
            # Update has_open_positions flag
            if not self.position_cache or not any(p.is_open for p in self.position_cache):
                self.has_open_positions = False
            
            self.last_risk_check = datetime.now()
        
        except Exception as e:
            self.logger.error(f"Error in fast monitoring: {e}")
    
    async def check_risk_and_positions(self):
        """Periodic risk check and automated position management (full version)"""
        try:
            # Get current positions
            positions = await self.order_manager.get_positions()
            self.position_cache = positions
            self.last_position_fetch = datetime.now()
            self.has_open_positions = len([p for p in positions if p.is_open]) > 0
            
            current_price = self.price_history[-1] if len(self.price_history) > 0 else 0
            
            # Note: ML-adaptive exits temporarily disabled
            # TODO: Re-implement adaptive exit manager if needed
            
            # Monitor positions with auto stop-loss/take-profit (instant -2%/+3% exits)
            risk_report = await self.risk_manager.monitor_positions()
            
            # Log alerts
            for alert in risk_report.get("alerts", []):
                if "LIQUIDATION" in alert or "EMERGENCY" in alert:
                    self.logger.error(alert)
                    self.alert_manager.alert_emergency(alert)
                else:
                    self.logger.warning(alert)
            
            # Log actions taken
            for action in risk_report.get("actions", []):
                self.logger.info(f"Auto-action: {action}")
                self.alert_manager.send_alert(action, "INFO")
            
            # Log risk metrics
            self.logger.info(f"Portfolio heat: {risk_report.get('portfolio_heat', 0):.1%}")
            self.logger.info(f"Daily drawdown: {risk_report.get('daily_drawdown', 0):.1%}")
            self.logger.info(f"Win rate: {risk_report.get('win_rate', 0):.1%}")
            self.logger.info(f"Kelly fraction: {risk_report.get('kelly_fraction', 0):.2f}")
            
            self.last_risk_check = datetime.now()
        
        except Exception as e:
            self.logger.error(f"Error in risk check: {e}", exc_info=True)
    
    async def display_status(self):
        """Display comprehensive bot status"""
        print("\n" + "="*80)
        print(f"⚡ Advanced Trading Bot Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # Account info
        try:
            account_info = await self.order_manager.get_account_info()
            
            # Parse nested account structure
            collateral = 0.0
            available = 0.0
            if isinstance(account_info, dict):
                if 'accounts' in account_info and len(account_info['accounts']) > 0:
                    acc_data = account_info['accounts'][0]
                    collateral = float(acc_data.get('collateral', 0))
                    available = float(acc_data.get('available_balance', 0))
                else:
                    collateral = float(account_info.get('collateral', 0))
                    available = float(account_info.get('available_balance', 0))
            
            print(f"\n💰 Account:")
            print(f"   Total Collateral: ${collateral:.2f}")
            print(f"   Available: ${available:.2f}")
        except Exception as e:
            print(f"   Error fetching account: {e}")
        
        # Positions
        try:
            positions = await self.order_manager.get_positions()
            print(f"\n📊 Positions: {len(positions)}")
            
            total_pnl = 0.0
            for pos in positions:
                if hasattr(pos, 'is_open') and pos.is_open:
                    side = "LONG" if pos.is_long else "SHORT"
                    pnl_symbol = "🟢" if pos.unrealized_pnl > 0 else "🔴"
                    symbol = settings.trading_symbol
                    print(f"   {pnl_symbol} Market {pos.market_id} ({symbol}): {side} {abs(pos.size):.4f}")
                    print(f"      Entry: ${pos.entry_price:.4f} | Current: ${pos.mark_price:.4f}")
                    print(f"      PnL: ${pos.unrealized_pnl:.2f} ({pos.pnl_percentage:+.2f}%)")
                    total_pnl += pos.unrealized_pnl
            
            if total_pnl != 0:
                pnl_color = "🟢" if total_pnl > 0 else "🔴"
                print(f"   {pnl_color} Total Unrealized PnL: ${total_pnl:.2f}")
        
        except Exception as e:
            print(f"   Error fetching positions: {e}")
        
        # Risk metrics
        try:
            portfolio_heat = await self.risk_manager.calculate_portfolio_heat()
            print(f"\n⚠️  Risk Metrics:")
            print(f"   Portfolio Heat: {portfolio_heat:.1%}")
            print(f"   Max Drawdown Today: {self.risk_manager.max_drawdown_today:.1%}")
            print(f"   Win Rate: {self.risk_manager.win_rate:.1%}")
            print(f"   Kelly Fraction: {self.risk_manager.calculate_kelly_size():.2f}")
        except Exception as e:
            print(f"   Error fetching risk metrics: {e}")
        
        # Performance
        uptime = datetime.now() - self.start_time
        print(f"\n📈 Performance:")
        print(f"   Uptime: {uptime.total_seconds() / 3600:.1f} hours")
        print(f"   Trades Executed: {self.trade_count}")
        print(f"   Active Strategies: WIN RATE OPTIMIZER (80%+ target)")
        
        # Win Rate Statistics (from tracker)
        try:
            stats = win_rate_tracker.get_statistics()
            if stats["total_trades"] > 0:
                win_rate = stats["win_rate"]
                if win_rate >= 80:
                    print(f"\n🎯 WIN RATE: {win_rate:.1f}% ✅ (TARGET ACHIEVED!)")
                else:
                    print(f"\n📊 WIN RATE: {win_rate:.1f}% (Target: 80%)")
                print(f"   Closed Trades: {stats['total_trades']} (W: {stats['winners']}, L: {stats['losers']})")
                print(f"   Total PnL: {'🟢' if stats['total_pnl'] > 0 else '🔴'} ${stats['total_pnl']:.2f}")
                print(f"   Profit Factor: {stats['profit_factor']:.2f}")
        except Exception as e:
            print(f"   Error fetching win rate stats: {e}")
        
        # Market data
        try:
            if len(self.price_history) >= 2:
                current_price = self.price_history[-1]
                price_change = ((current_price - self.price_history[0]) / self.price_history[0]) * 100
                change_symbol = "📈" if price_change > 0 else "📉"
                
                print(f"\n{change_symbol} Market ({settings.trading_symbol}):")
                print(f"   Current Price: ${current_price:.4f}")
                print(f"   24h Change: {price_change:+.2f}%")
                print(f"   Data Points: {len(self.price_history)}")
        except Exception as e:
            print(f"   Error displaying market data: {e}")
        
        print("="*80 + "\n")
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signal"""
        self.logger.info("Shutdown signal received")
        self.running = False
    
    async def start(self):
        """Start the advanced trading bot"""
        self.logger.info("Starting Advanced Trading Bot...")
        
        # Check trading mode
        if settings.trading_symbol == "MULTI-TOP-3":
            self.logger.info("🎯 TOP 3 HIGH-VOLUME MODE DETECTED")
            self.logger.info("Focus: ETH-PERP, BTC-PERP, SOL-PERP for 2% quick exits")
            # Initialize Top 3 scanner
            await initialize_top3_scanner()
            self.logger.info("✓ Top 3 High-Volume Scanner ready!")
            market_id = 0  # Primary market (ETH-PERP)
            
        else:
            # CRITICAL: Resolve market metadata at startup for single-market mode
            self.logger.info(f"Resolving market metadata for {settings.trading_symbol} (Market ID: {settings.trading_market_id})...")
            client = await get_client()
            
            # Try to resolve using both symbol and market_id
            market_id = await resolve_market_metadata(
                client, 
                symbol=settings.trading_symbol,
                market_id=settings.trading_market_id
            )
            
            if market_id is None:
                self.logger.error(f"Failed to resolve market metadata")
                self.logger.error("Bot cannot start without valid market metadata")
                return
            
            # Update settings with resolved market_id (in case it was corrected)
            if market_id != settings.trading_market_id:
                self.logger.warning(f"Config has market_id={settings.trading_market_id}, resolved to {market_id}")
                settings.trading_market_id = market_id
        
        # Display market info (skip for multi-market modes)
        if settings.trading_symbol not in ["ULTRA-DYNAMIC", "MULTI-TOP-3"]:
            market_info = market_metadata.get_market(market_id)
            if market_info:
                detected_symbol = market_info.get('symbol', settings.trading_symbol)
                self.logger.info(f"✓ Market: {detected_symbol} (ID: {market_id})")
                self.logger.info(f"  Base decimals: {market_info['base_decimals']}")
                self.logger.info(f"  Price decimals: {market_info['price_decimals']}")
        
        # Update symbol if it was auto-detected (only for single-market mode)
        if settings.trading_symbol not in ["ULTRA-DYNAMIC", "MULTI-TOP-3"]:
            market_info = market_metadata.get_market(market_id)
            if market_info:
                detected_symbol = market_info.get('symbol', settings.trading_symbol)
                if detected_symbol != settings.trading_symbol:
                    self.logger.info(f"  Auto-detected symbol: {detected_symbol}")
                    settings.trading_symbol = detected_symbol
        
        # Check for dry run mode
        if settings.dry_run:
            self.logger.warning("=" * 60)
            self.logger.warning("🔵 DRY RUN MODE - NO REAL TRADES WILL BE EXECUTED")
            self.logger.warning("=" * 60)
        
        # Check for testnet
        if settings.use_testnet:
            self.logger.warning("Using TESTNET")
        else:
            self.logger.warning("⚠️  Trading on MAINNET with REAL funds!")
        
        # Different messages for ultra-dynamic vs single-market mode
        if settings.trading_symbol == "ULTRA-DYNAMIC":
            self.logger.info("🎯 ULTRA-DYNAMIC MODE: Scanning top 10 highest volume tokens")
        else:
            self.logger.info(f"Trading {settings.trading_symbol} on market ID {settings.trading_market_id}")
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        self.running = True
        self.logger.info("Bot started successfully")
        self.alert_manager.send_alert("Advanced Trading Bot started", "INFO")
        
        # CRITICAL: Check for existing positions on startup and set adaptive monitoring flag
        try:
            existing_positions = await self.order_manager.get_positions()
            open_positions = [p for p in existing_positions if p.is_open]
            if open_positions:
                self.has_open_positions = True
                self.logger.warning(f"🔥 DETECTED {len(open_positions)} EXISTING OPEN POSITION(S) - ENABLING 1-SECOND FAST MONITORING!")
                for pos in open_positions:
                    self.logger.warning(f"   Position: {pos.size:.4f} @ ${pos.entry_price:.2f}, PnL: {pos.pnl_percentage:.2f}%")
            else:
                self.logger.info("No existing positions detected - using 5-second monitoring")
        except Exception as e:
            self.logger.error(f"Error checking existing positions: {e}")
        
        # Initial status display - commented out temporarily to debug
        # self.logger.info("Calling display_status()...")
        # await self.display_status()
        # self.logger.info("Display status completed, entering main loop...")
        self.logger.info("Entering main trading loop...")
        
        # Main trading loop
        iteration = 0
        start_time = datetime.now()
        
        while self.running:
            try:
                iteration += 1
                
                # Update uptime metric
                uptime = (datetime.now() - start_time).total_seconds()
                bot_metrics.set_uptime(uptime)
                
                # Update market data history
                await self.update_market_data_history()
                
                # Update market metrics
                if len(self.price_history) > 0:
                    current_price = self.price_history[-1]
                    bot_metrics.set_market_price(
                        market=str(settings.trading_market_id),
                        symbol=settings.trading_symbol,
                        price=current_price
                    )
                
                # Run trading strategies every 5 seconds (FAST for 1m scalping!)
                if (datetime.now() - self.last_strategy_run).seconds >= 5:
                    await self.run_strategies()
                
                # CRITICAL: ALWAYS run position monitoring (OCO or not)
                # Bot logic is ALWAYS ACTIVE to handle:
                # 1. Backup -2% stop loss if OCO fails
                # 2. Portfolio overheat (>60%) immediate closes
                # 3. Trailing stops and early exits
                check_interval = 1 if self.has_open_positions else 5
                if (datetime.now() - self.last_risk_check).total_seconds() >= check_interval:
                    # Fast check without excessive logging when positions are open
                    if self.has_open_positions:
                        await self.check_risk_and_positions_fast()
                    else:
                        await self.check_risk_and_positions()
                    self.last_risk_check = datetime.now()
                
                # Update account balance metric (only every 60 seconds to save API calls)
                if iteration % 12 == 0:  # Every 12 iterations × 5s = 60 seconds
                    try:
                        account_info = await self.order_manager.get_account_info()
                        if isinstance(account_info, dict):
                            if 'accounts' in account_info and len(account_info['accounts']) > 0:
                                balance = float(account_info['accounts'][0].get('collateral', 0))
                            else:
                                balance = float(account_info.get('collateral', 0))
                            bot_metrics.set_account_balance(balance)
                    except Exception as e:
                        self.logger.debug(f"Error updating balance metric: {e}")
                
                # Display status every 30 iterations (~2.5 minutes if 5s sleep)
                if iteration % 30 == 0:
                    await self.display_status()
                
                # ADAPTIVE SLEEP: 1s when positions open (critical TP/SL), 5s when idle (save resources)
                sleep_interval = 1 if self.has_open_positions else 5
                await asyncio.sleep(sleep_interval)
            
            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                bot_metrics.record_error(error_type=type(e).__name__, component="main_loop")
                self.alert_manager.alert_error(str(e))
                await asyncio.sleep(30)  # Wait on error
        
        await self.stop()
    
    async def stop(self):
        """Stop the trading bot gracefully"""
        self.logger.info("Stopping Advanced Trading Bot...")
        
        self.running = False
        
        # Final status
        await self.display_status()
        
        # Close all connections
        await close_client()
        
        # Send shutdown alert
        self.alert_manager.send_alert("Advanced Trading Bot stopped", "INFO")
        
        self.logger.info("Bot stopped gracefully")


async def main():
    """Main entry point"""
    # Validate configuration
    if not settings.lighter_api_key_private_key:
        print("❌ Error: LIGHTER_API_KEY_PRIVATE_KEY must be set in .env file")
        print("Copy .env.example to .env and configure your API credentials")
        sys.exit(1)
    
    if not settings.lighter_account_index:
        print("❌ Error: LIGHTER_ACCOUNT_INDEX must be set in .env file")
        sys.exit(1)
    
    print("🚀 Starting Advanced Trading Bot...")
    print(f"📍 Network: {settings.lighter_base_url}")
    print(f"🎯 Trading: {settings.trading_symbol} (Market ID: {settings.trading_market_id})")
    print(f"⚠️  WARNING: Trading on {'MAINNET' if 'mainnet' in settings.lighter_base_url else 'TESTNET'} with REAL funds!")
    print()
    
    # Create and start bot
    bot = AdvancedTradingBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())

