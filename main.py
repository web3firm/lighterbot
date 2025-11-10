"""
Advanced Trading Bot with Multiple Strategies
"""
import asyncio
import signal
import sys
from typing import Optional, List
from datetime import datetime
from config import settings
from market_data import MarketData
from order_manager import OrderManager
from risk_manager import AdvancedRiskManager, Position
from strategies import (
    StrategyManager, MomentumStrategy, MeanReversionStrategy,
    MarketMakingStrategy, GridTradingStrategy, OrderFlowStrategy,
    SentimentStrategy, MarketData as StrategyMarketData,
    Signal, SignalType
)
from logger import get_logger, get_alert_manager
from lighter_client import close_client


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
        
        self.market_data = MarketData()
        self.order_manager = OrderManager()
        self.risk_manager = AdvancedRiskManager(self.order_manager, self.market_data)
        
        # Initialize strategy manager
        self.strategy_manager = StrategyManager()
        
        # Add strategies based on configuration
        if settings.enable_momentum_strategy:
            self.strategy_manager.add_strategy(MomentumStrategy())
            self.logger.info("✓ Enabled: Momentum Strategy")
        
        if settings.enable_mean_reversion_strategy:
            self.strategy_manager.add_strategy(MeanReversionStrategy())
            self.logger.info("✓ Enabled: Mean Reversion Strategy")
        
        if settings.enable_market_making_strategy:
            self.strategy_manager.add_strategy(MarketMakingStrategy())
            self.logger.info("✓ Enabled: Market Making Strategy")
        
        if settings.enable_grid_trading_strategy:
            self.strategy_manager.add_strategy(GridTradingStrategy())
            self.logger.info("✓ Enabled: Grid Trading Strategy")
        
        if settings.enable_orderflow_strategy:
            self.strategy_manager.add_strategy(OrderFlowStrategy())
            self.logger.info("✓ Enabled: Order Flow Strategy")
        
        if settings.enable_sentiment_strategy:
            # Extract symbol from trading symbol (e.g., "BTC-PERP" -> "BTC")
            symbol = settings.trading_symbol.split('-')[0]
            self.strategy_manager.add_strategy(SentimentStrategy(symbol))
            self.logger.info(f"✓ Enabled: Sentiment Strategy ({symbol})")

        # self.strategy_manager.add_strategy(GridTradingStrategy())   # Uncomment for grid trading
        
        # Bot state
        self.running = False
        self.last_risk_check = datetime.now()
        self.last_strategy_run = datetime.now()
        
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
        Execute a trading signal
        
        Args:
            signal: Trading signal from strategy
            
        Returns:
            True if order was executed
        """
        try:
            # Determine order parameters
            size = settings.min_order_size * signal.strength  # Scale size by signal strength
            
            # Calculate stop-loss price (2% away)
            stop_loss_pct = 0.02
            if signal.signal_type == SignalType.BUY:
                stop_loss_price = signal.price * (1 - stop_loss_pct)
            else:
                stop_loss_price = signal.price * (1 + stop_loss_pct)
            
            # Risk check with position sizing
            approved, reason, adjusted_size = await self.risk_manager.check_order_risk(
                side="buy" if signal.signal_type == SignalType.BUY else "sell",
                size=size,
                price=signal.price,
                market_id=settings.trading_market_id,
                stop_loss=stop_loss_price
            )
            
            if not approved:
                self.logger.warning(f"Order rejected by risk manager: {reason}")
                return False
            
            # Place order
            side = "buy" if signal.signal_type == SignalType.BUY else "sell"
            
            self.logger.info(f"Executing {side.upper()} order: size={adjusted_size:.4f} @ ${signal.price:.2f}")
            self.logger.info(f"Reason: {signal.reason}")
            
            order = await self.order_manager.place_market_order(
                side=side,
                size=adjusted_size,
                market_id=settings.trading_market_id
            )
            
            if order:
                self.trade_count += 1
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
        """Run all trading strategies and execute signals"""
        try:
            # Check if we have enough price history
            if len(self.price_history) < 30:
                self.logger.debug("Not enough price history for strategy analysis")
                return
            
            # Create market data snapshot for strategies
            current_price = self.price_history[-1]
            bid, ask = await self.market_data.get_best_bid_ask()
            
            market_snapshot = StrategyMarketData(
                symbol=settings.trading_symbol,
                price=current_price,
                bid=bid,
                ask=ask,
                spread=ask - bid,
                volume_24h=0.0,  # Would fetch from exchange
                price_history=self.price_history.copy(),
                high_history=self.high_history.copy(),
                low_history=self.low_history.copy(),
                volume_history=self.volume_history.copy(),
                timestamp=datetime.now()
            )
            
            # Analyze market with all strategies
            signals = await self.strategy_manager.analyze_market(market_snapshot)
            
            if not signals:
                self.logger.debug("No trading signals generated")
                return
            
            # Get consensus signal
            consensus = self.strategy_manager.get_consensus_signal(signals)
            
            if consensus:
                self.logger.info(f"Consensus signal: {consensus.signal_type.value} (strength={consensus.strength:.2f})")
                self.logger.info(f"Reason: {consensus.reason}")
                
                # Check if we already have a position
                position = await self.order_manager.get_position(settings.trading_market_id)
                
                if position and position.is_open:
                    # Don't open conflicting positions
                    if (position.is_long and consensus.signal_type == SignalType.SELL) or \
                       (not position.is_long and consensus.signal_type == SignalType.BUY):
                        self.logger.info("Conflicting signal with open position, skipping")
                        return
                
                # Execute the consensus signal
                await self.execute_signal(consensus)
            
            self.last_strategy_run = datetime.now()
        
        except Exception as e:
            self.logger.error(f"Error running strategies: {e}", exc_info=True)
    
    async def check_risk_and_positions(self):
        """Periodic risk check and automated position management"""
        try:
            # Monitor positions with auto stop-loss/take-profit
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
                    print(f"   {pnl_symbol} Market {pos.market_id} ({pos.symbol}): {side} {abs(pos.size):.4f}")
                    print(f"      Entry: ${pos.entry_price:.4f} | Current: ${pos.current_price:.4f}")
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
        print(f"   Active Strategies: {len([s for s in self.strategy_manager.strategies if s.enabled])}")
        
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
        self.logger.info(f"Trading {settings.trading_symbol} on market ID {settings.trading_market_id}")
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        self.running = True
        self.logger.info("Bot started successfully")
        self.alert_manager.send_alert("Advanced Trading Bot started", "INFO")
        
        # Initial status display
        await self.display_status()
        
        # Main trading loop
        iteration = 0
        while self.running:
            try:
                iteration += 1
                
                # Update market data history
                await self.update_market_data_history()
                
                # Run trading strategies every 60 seconds
                if (datetime.now() - self.last_strategy_run).seconds >= 60:
                    await self.run_strategies()
                
                # Risk check and position monitoring every 5 minutes
                if (datetime.now() - self.last_risk_check).seconds >= 300:
                    await self.check_risk_and_positions()
                
                # Display status every 30 iterations (~15 minutes if 30s sleep)
                if iteration % 30 == 0:
                    await self.display_status()
                
                # Sleep before next iteration
                await asyncio.sleep(30)  # Check every 30 seconds
            
            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                self.alert_manager.alert_error(str(e))
                await asyncio.sleep(60)  # Wait longer on error
        
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

