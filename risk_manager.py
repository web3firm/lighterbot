"""
Advanced Risk Management System with Intelligent Early Exit Detection
"""
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import math

from order_manager import OrderManager
from market_data import MarketData
from config import settings
from logger import logger
from trade_validator import TradeValidator


@dataclass
class RiskLimits:
    """Enhanced risk limit configuration with safety features"""
    max_position_size: float
    max_leverage: int
    max_daily_drawdown: float
    liquidation_threshold: float
    max_open_orders: int
    min_margin_ratio: float = 0.2
    max_portfolio_heat: float = 0.5  # Max 50% total collateral (allows 5x 10% positions)
    max_correlation_exposure: float = 0.5  # Max 50% in correlated positions
    
    # ENHANCED SAFETY LIMITS
    max_single_trade_loss: float = 0.02  # Max 2% loss per trade
    max_position_exposure: float = 0.25  # Max 25% collateral per position (allows 20% × 10x)
    max_concurrent_positions: int = 5  # Max 5 positions at once
    min_profit_target: float = 0.01  # Minimum 1% profit target
    max_daily_trades: int = 50  # Max 50 trades per day (high volume)
    cooldown_after_loss: int = 30  # 30 sec cooldown after loss
    consecutive_loss_limit: int = 5  # Stop after 5 consecutive losses
    emergency_stop_drawdown: float = 0.10  # Emergency stop at 10% drawdown


@dataclass
class Position:
    """Position data"""
    market_id: int
    symbol: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    pnl_percentage: float
    leverage: float
    liquidation_price: Optional[float]
    is_long: bool
    is_open: bool


class AdvancedRiskManager:
    """
    Advanced risk management with:
    - Kelly Criterion position sizing
    - Drawdown protection
    - Auto stop-loss/take-profit
    - Portfolio heat monitoring
    - Risk-adjusted returns tracking
    """
    
    def __init__(self, order_manager: OrderManager, market_data: MarketData):
        self.order_manager = order_manager
        self.market_data = market_data
        self.logger = logger  # Add logger instance
        
        # Risk limits from config
        self.limits = RiskLimits(
            max_position_size=settings.max_position_size,
            max_leverage=settings.max_leverage,
            max_daily_drawdown=settings.max_daily_drawdown,
            liquidation_threshold=settings.liquidation_threshold,
            max_open_orders=settings.max_open_orders
        )
        
        self.daily_start_balance = None
        self.daily_high_balance = None
        self.max_drawdown_today = 0.0
        
        # Performance tracking
        self.win_rate = 0.5  # Start with 50% assumption
        self.avg_win = 0.02  # 2%
        self.avg_loss = 0.01  # 1%
        self.trade_history = []
        
        # INTELLIGENT TRADE VALIDATION (Early Exit Detection)
        self.trade_validator = TradeValidator()
        self.logger.info("✅ Trade Validator initialized (early exit detection enabled)")
        
        # ACCOUNT INFO CACHE (reduce rate limit issues)
        self.account_cache = None
        self.account_cache_time = datetime.now() - timedelta(seconds=100)
    
    def calculate_kelly_size(
        self,
        win_rate: Optional[float] = None,
        win_loss_ratio: Optional[float] = None,
        max_fraction: float = 0.25
    ) -> float:
        """
        Calculate position size using Kelly Criterion
        
        Kelly % = (Win Rate * Win/Loss Ratio - Loss Rate) / Win/Loss Ratio
        
        Args:
            win_rate: Historical win rate (0-1)
            win_loss_ratio: Average win / Average loss
            max_fraction: Maximum fraction of Kelly to use (0.25 = quarter Kelly)
            
        Returns:
            Position size as fraction of capital
        """
        win_rate = win_rate or self.win_rate
        win_loss_ratio = win_loss_ratio or (self.avg_win / self.avg_loss) if self.avg_loss > 0 else 2.0
        
        loss_rate = 1 - win_rate
        
        # Kelly formula
        kelly_fraction = (win_rate * win_loss_ratio - loss_rate) / win_loss_ratio
        
        # Apply safety factor (use fraction of Kelly)
        kelly_fraction = max(0, min(kelly_fraction, 1.0))  # Clamp 0-1
        safe_kelly = kelly_fraction * max_fraction
        
        return safe_kelly
    
    async def calculate_position_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss_price: float = None,  # Now optional
        risk_per_trade: float = 0.02,  # Legacy parameter, not used in new method
        market_id: Optional[int] = None
    ) -> float:
        """
        Calculate position size as percentage of account balance with leverage
        
        CORRECTED: Tracks collateral usage properly and ensures total portfolio usage <= 50%
        
        Formula:
        - Desired notional = account_balance × position_percent × leverage
        - Collateral for this position = notional / leverage
        - Check: existing_collateral + new_collateral <= 50% of account
        
        Args:
            account_balance: Total account balance in USD
            entry_price: Entry price per coin
            stop_loss_price: Stop loss price (not used in percentage-based sizing)
            risk_per_trade: Legacy parameter (not used)
            market_id: Market ID (to get min size from API)
            
        Returns:
            Position size in base currency (coins)
        """
        from config import settings
        from utils import market_metadata
        
        # Get percentage-based settings
        position_percent = settings.position_size_percent / 100.0  # e.g., 0.10 for 10%
        leverage = settings.leverage  # e.g., 5x
        
        # Calculate desired notional position value (this is the market exposure)
        desired_notional_usd = account_balance * position_percent * leverage
        
        # Calculate collateral required for this position
        # With leverage, collateral = notional / leverage
        this_position_collateral = desired_notional_usd / leverage
        
        # CRITICAL: Get existing collateral usage from all open positions
        existing_collateral_used = await self._get_total_collateral_used()
        
        # Calculate available collateral (max_collateral% cap from settings)
        # With 5x leverage: 14% collateral = 70% buying power usage (safe!)
        max_collateral_percent = settings.max_collateral / 100.0  # e.g., 0.14 for 14%
        max_total_collateral = account_balance * max_collateral_percent
        available_collateral = max_total_collateral - existing_collateral_used
        
        self.logger.info(
            f"💰 Collateral check: Existing=${existing_collateral_used:.2f}, "
            f"This position=${this_position_collateral:.2f}, "
            f"Available=${available_collateral:.2f} (Max={max_total_collateral:.2f}, "
            f"{max_collateral_percent*100:.0f}% × {leverage}x = {max_collateral_percent*leverage*100:.0f}% buying power)"
        )
        
        # Check if we have enough available collateral
        if available_collateral <= 0:
            self.logger.warning(
                f"🛑 POSITION BLOCKED: Already using ${existing_collateral_used:.2f} collateral. "
                f"Max allowed is ${max_total_collateral:.2f} ({max_collateral_percent*100:.0f}% of ${account_balance:.2f}). "
                f"No available collateral for new positions."
            )
            return 0.0  # Return 0 to block position opening
        
        # If requested collateral exceeds available, reduce to available
        if this_position_collateral > available_collateral:
            self.logger.warning(
                f"⚠️ Requested collateral ${this_position_collateral:.2f} exceeds available ${available_collateral:.2f}. "
                f"Reducing position size to fit within {max_collateral_percent*100:.0f}% portfolio cap."
            )
            this_position_collateral = available_collateral
            # Recalculate notional from capped collateral
            desired_notional_usd = this_position_collateral * leverage
        
        # Convert notional to coins
        position_size_coins = desired_notional_usd / entry_price
        
        # Get minimum order size from API metadata
        if market_id:
            min_size = market_metadata.get_min_order_size(market_id)
        else:
            min_size = 0.001  # Fallback
        
        # Ensure minimum viable size
        if position_size_coins < min_size:
            self.logger.warning(
                f"⚠️ Calculated position {position_size_coins:.6f} below minimum {min_size:.6f}. "
                f"This would require ${min_size * entry_price:.2f} collateral (with {leverage}x leverage). "
                f"Skipping position to preserve capital."
            )
            return 0.0  # Don't force minimum if it would exceed collateral budget
        
        # Cap at max position size (safety check)
        final_size = min(position_size_coins, self.limits.max_position_size)
        
        # Calculate final collateral and notional
        final_notional = final_size * entry_price
        final_collateral = final_notional / leverage
        
        self.logger.info(
            f"✅ Position sizing: ${account_balance:.2f} × {settings.position_size_percent}% × {leverage}x "
            f"= ${final_notional:.2f} notional (${final_collateral:.2f} collateral) "
            f"= {final_size:.6f} coins @ ${entry_price:.2f}"
        )
        self.logger.info(
            f"📊 Portfolio usage: ${existing_collateral_used:.2f} + ${final_collateral:.2f} "
            f"= ${existing_collateral_used + final_collateral:.2f} / ${max_total_collateral:.2f} "
            f"({((existing_collateral_used + final_collateral) / account_balance * 100):.1f}% of account)"
        )
        
        return final_size
    
    async def _get_total_collateral_used(self) -> float:
        """
        Calculate total collateral currently used by all open positions
        
        Returns:
            Total collateral in USD
        """
        try:
            positions = await self.order_manager.get_positions()
            
            if not positions:
                self.logger.debug("No open positions found")
                return 0.0
            
            total_collateral = 0.0
            for pos in positions:
                if pos.is_open:
                    # Use mark_price (current price from API) not current_price
                    position_notional = abs(pos.size * pos.mark_price)
                    position_collateral = position_notional / pos.leverage if pos.leverage > 0 else position_notional
                    total_collateral += position_collateral
                    self.logger.debug(
                        f"Position on market {pos.market_id}: "
                        f"size={pos.size:.6f}, price=${pos.mark_price:.2f}, "
                        f"notional=${position_notional:.2f}, collateral=${position_collateral:.2f}"
                    )
            
            self.logger.debug(f"Total collateral used across {len(positions)} positions: ${total_collateral:.2f}")
            return total_collateral
            
        except Exception as e:
            self.logger.error(f"Error calculating total collateral: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            # CRITICAL: Return large number to block new positions on error (fail-safe)
            return 999999.0  # Fail-safe: block new positions if we can't verify existing usage
    
    def calculate_trading_cost(
        self, 
        size: float, 
        price: float, 
        market_id: int,
        is_maker: bool = False
    ) -> float:
        """
        Calculate trading cost including fees from API metadata
        
        Args:
            size: Position size
            price: Entry price
            market_id: Market ID
            is_maker: True if maker order, False if taker
            
        Returns:
            Trading cost in quote currency
        """
        from utils import market_metadata
        
        position_value = size * price
        fees = market_metadata.get_fees(market_id)
        fee_rate = fees["maker"] if is_maker else fees["taker"]
        
        # Convert fee percentage to decimal (API returns as percentage)
        fee_cost = position_value * (fee_rate / 100.0)
        
        return fee_cost
    
    async def check_order_risk(
        self,
        side: str,
        size: float,
        price: float,
        market_id: Optional[int] = None,
        stop_loss: Optional[float] = None
    ) -> Tuple[bool, str, float]:
        """
        ENHANCED: Advanced risk check with comprehensive safety features
        
        Safety checks:
        1. Account balance validation
        2. Position size limits
        3. Portfolio heat (exposure)
        4. Daily drawdown protection
        5. Consecutive loss protection
        6. Daily trade limit
        7. Cooldown after losses
        8. Emergency stop conditions
        
        Returns:
            (approved, reason, adjusted_size) tuple
        """
        try:
            # Use cached account info to avoid rate limits
            now = datetime.now()
            if (now - self.account_cache_time).total_seconds() >= 60 or self.account_cache is None:
                self.account_cache = await self.order_manager.get_account_info()
                self.account_cache_time = now
            
            account_info = self.account_cache
            
            # Parse account balance from nested structure
            account_balance = 0.0
            if isinstance(account_info, dict):
                if 'accounts' in account_info and len(account_info['accounts']) > 0:
                    acc_data = account_info['accounts'][0]
                    account_balance = float(acc_data.get('collateral', 0))
                elif 'collateral' in account_info:
                    account_balance = float(account_info.get('collateral', 0))
            
            if account_balance == 0:
                return False, "❌ Account balance is zero", 0.0
            
            # SAFETY CHECK 1: Emergency Stop - Daily Drawdown Exceeded
            if hasattr(self, 'max_drawdown_today') and self.max_drawdown_today >= self.limits.emergency_stop_drawdown:
                return False, f"🛑 EMERGENCY STOP: Daily drawdown {self.max_drawdown_today:.1%} >= {self.limits.emergency_stop_drawdown:.1%}", 0.0
            
            # SAFETY CHECK 2: Consecutive Loss Protection
            recent_trades = self.trade_history[-self.limits.consecutive_loss_limit:] if len(self.trade_history) >= self.limits.consecutive_loss_limit else []
            if len(recent_trades) == self.limits.consecutive_loss_limit:
                if all(t.get('result') == 'loss' for t in recent_trades):
                    return False, f"⛔ Consecutive loss limit reached ({self.limits.consecutive_loss_limit} losses). Cooling down.", 0.0
            
            # SAFETY CHECK 3: Cooldown After Recent Loss
            if len(self.trade_history) > 0:
                last_trade = self.trade_history[-1]
                if last_trade.get('result') == 'loss':
                    time_since_loss = (datetime.now() - last_trade.get('timestamp', datetime.now())).total_seconds()
                    if time_since_loss < self.limits.cooldown_after_loss:
                        remaining = int(self.limits.cooldown_after_loss - time_since_loss)
                        return False, f"⏳ Cooldown active: {remaining}s remaining after loss", 0.0
            
            # SAFETY CHECK 4: Daily Trade Limit
            today_trades = [t for t in self.trade_history if (datetime.now() - t.get('timestamp', datetime.min)).days == 0]
            if len(today_trades) >= self.limits.max_daily_trades:
                return False, f"📊 Daily trade limit reached ({self.limits.max_daily_trades} trades)", 0.0
            
            # SAFETY CHECK 5: Maximum Open Positions
            open_positions = await self.order_manager.get_positions()
            open_count = len([p for p in open_positions if p.is_open]) if open_positions else 0
            if open_count >= self.limits.max_concurrent_positions:
                return False, f"📈 Max concurrent positions reached ({self.limits.max_concurrent_positions})", 0.0
            
            # Calculate risk-adjusted position size
            # NEW: Prioritize percentage-based sizing over stop-loss-based
            if size == 0:
                # Use percentage-based position sizing (modern approach)
                optimal_size = await self.calculate_position_size(
                    account_balance=account_balance,
                    entry_price=price,
                    stop_loss_price=stop_loss,  # Optional, not used in percentage method
                    market_id=market_id
                )
                size = optimal_size
            elif stop_loss and size > 0:
                # Validate provided size against stop-loss risk
                optimal_size = await self.calculate_position_size(
                    account_balance=account_balance,
                    entry_price=price,
                    stop_loss_price=stop_loss,
                    market_id=market_id
                )
                if size > optimal_size * 1.5:  # Allow 50% buffer
                    logger.warning(f"⚠️ Requested size {size:.4f} exceeds optimal {optimal_size:.4f}, adjusting")
                    size = optimal_size
            
            # Fallback check
            if size == 0:
                return False, "❌ Cannot calculate position size - check config", 0.0
            
            # SAFETY CHECK 6: Position Size Limit
            if size > self.limits.max_position_size:
                return False, f"📏 Order size {size} exceeds max {self.limits.max_position_size}", 0.0
            
            # SAFETY CHECK 7: Single Position Collateral Exposure Limit
            # With leverage, we use collateral (not notional) for exposure calculation
            from config import settings as config_settings
            position_value = size * price
            collateral_used = position_value / config_settings.leverage  # Actual collateral needed
            position_exposure = collateral_used / account_balance
            if position_exposure > self.limits.max_position_exposure:
                return False, f"⚠️ Position collateral {position_exposure:.1%} exceeds max {self.limits.max_position_exposure:.1%}", 0.0
            
            # SAFETY CHECK 8: Portfolio Heat (Total Risk Exposure based on collateral)
            portfolio_heat = await self.calculate_portfolio_heat()
            order_heat = collateral_used / account_balance
            
            if portfolio_heat + order_heat > self.limits.max_portfolio_heat:
                return False, f"🔥 Portfolio heat {(portfolio_heat + order_heat):.1%} exceeds max {self.limits.max_portfolio_heat:.1%}", 0.0
            
            # SAFETY CHECK 9: Minimum Profit Target Validation
            # Ensure trade has reasonable profit potential
            if stop_loss:
                risk_amount = abs(price - stop_loss) / price
                if risk_amount > 0:
                    # Risk/Reward should be at least 1:2 (risk 1% to make 2%)
                    min_profit_for_risk = risk_amount * 2
                    if min_profit_for_risk < self.limits.min_profit_target:
                        logger.warning(f"⚠️ Profit target {min_profit_for_risk:.2%} below minimum {self.limits.min_profit_target:.2%}")
            
            # All safety checks passed!
            logger.info(f"✅ RISK CHECKS PASSED:")
            logger.info(f"   💰 Account: ${account_balance:.2f}")
            logger.info(f"   📊 Position size: {size:.4f} (${position_value:.2f})")
            logger.info(f"   📈 Position exposure: {position_exposure:.1%}")
            logger.info(f"   🔥 Portfolio heat: {portfolio_heat:.1%} + {order_heat:.1%} = {(portfolio_heat + order_heat):.1%}")
            logger.info(f"   📉 Daily drawdown: {self.max_drawdown_today:.1%}")
            logger.info(f"   🎯 Open positions: {open_count}/{self.limits.max_concurrent_positions}")
            logger.info(f"   📅 Today's trades: {len(today_trades)}/{self.limits.max_daily_trades}")
            
            return True, "All safety checks passed", size
            if self.max_drawdown_today >= self.limits.max_daily_drawdown:
                return False, f"Daily drawdown {self.max_drawdown_today:.1%} limit reached", 0.0
            
            # Check open orders count
            active_orders = await self.order_manager.get_active_orders(market_id)
            if len(active_orders) >= self.limits.max_open_orders:
                return False, f"Open orders {len(active_orders)} exceeds max {self.limits.max_open_orders}", 0.0
            
            return True, "Risk check passed", size
            
        except Exception as e:
            logger.error(f"Error in risk check: {e}")
            return False, f"Risk check error: {e}", 0.0
    
    async def calculate_portfolio_heat(self) -> float:
        """
        Calculate total portfolio heat (collateral usage)
        
        With leverage, we track collateral used, not notional exposure.
        
        Returns:
            Portfolio heat as fraction (0-1) based on collateral usage
        """
        try:
            positions = await self.order_manager.get_positions()
            
            # Use cached account info to avoid rate limits
            now = datetime.now()
            if (now - self.account_cache_time).total_seconds() >= 60 or self.account_cache is None:
                self.account_cache = await self.order_manager.get_account_info()
                self.account_cache_time = now
            
            account_info = self.account_cache
            
            # Parse account balance from nested structure
            account_balance = 0.0
            if isinstance(account_info, dict):
                if 'accounts' in account_info and len(account_info['accounts']) > 0:
                    acc_data = account_info['accounts'][0]
                    account_balance = float(acc_data.get('collateral', 0))
                elif 'collateral' in account_info:
                    account_balance = float(account_info.get('collateral', 0))
            
            if account_balance == 0:
                return 0.0
            
            # Use collateral (margin) instead of notional exposure
            total_collateral_used = sum(p.margin for p in positions if hasattr(p, 'margin'))
            return total_collateral_used / account_balance
            
        except Exception as e:
            logger.error(f"Error calculating portfolio heat: {e}")
            return 0.0
    
    async def auto_stop_loss_take_profit(
        self,
        market_id: int,
        position: Position,
        stop_loss_pct: float = -2.0,
        take_profit_pct: float = 4.0
    ) -> bool:
        """
        Automatically close position if stop-loss or take-profit hit
        
        Args:
            market_id: Market ID
            position: Position data
            stop_loss_pct: Stop loss percentage (negative)
            take_profit_pct: Take profit percentage (positive)
            
        Returns:
            True if position was closed
        """
        try:
            if not position.is_open:
                self.logger.debug(f"Position {market_id} is not open, skipping SL/TP check")
                return False
            
            # Log current PnL state
            self.logger.debug(
                f"SL/TP check: Market {market_id}, PnL {position.pnl_percentage:.2f}%, "
                f"SL threshold {stop_loss_pct:.2f}%, TP threshold {take_profit_pct:.2f}%"
            )
            
            # Check stop-loss
            if position.pnl_percentage <= stop_loss_pct:
                self.logger.warning(
                    f"🛑 STOP-LOSS TRIGGERED for market {market_id}: "
                    f"PnL {position.pnl_percentage:.2f}% <= {stop_loss_pct:.2f}%"
                )
                
                # Close position
                side = "sell" if position.is_long else "buy"
                self.logger.info(f"Executing stop-loss: {side.upper()} {abs(position.size)} @ market")
                
                success = await self.order_manager.place_market_order(
                    side=side,
                    size=abs(position.size),
                    market_id=market_id
                )
                
                if success:
                    # Track trade result
                    self.trade_history.append({
                        'result': 'loss',
                        'pnl_pct': position.pnl_percentage,
                        'timestamp': datetime.now()
                    })
                    self.update_statistics()
                    self.logger.info(f"✅ Stop-loss executed successfully")
                    return True
                else:
                    self.logger.error(f"❌ Failed to execute stop-loss order")
                    return False
            
            # Check take-profit
            if position.pnl_percentage >= take_profit_pct:
                self.logger.info(
                    f"🎯 TAKE-PROFIT TRIGGERED for market {market_id}: "
                    f"PnL {position.pnl_percentage:.2f}% >= {take_profit_pct:.2f}%"
                )
                
                # Close position
                side = "sell" if position.is_long else "buy"
                self.logger.info(f"Executing take-profit: {side.upper()} {abs(position.size)} @ market")
                
                success = await self.order_manager.place_market_order(
                    side=side,
                    size=abs(position.size),
                    market_id=market_id
                )
                
                if success:
                    # Track trade result
                    self.trade_history.append({
                        'result': 'win',
                        'pnl_pct': position.pnl_percentage,
                        'timestamp': datetime.now()
                    })
                    self.update_statistics()
                    self.logger.info(f"✅ Take-profit executed successfully")
                    return True
                else:
                    self.logger.error(f"❌ Failed to execute take-profit order")
                    return False
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in auto stop-loss/take-profit: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def update_statistics(self):
        """Update win rate and average win/loss from trade history"""
        if not self.trade_history:
            return
        
        recent_trades = self.trade_history[-50:]  # Last 50 trades
        
        wins = [t for t in recent_trades if t['result'] == 'win']
        losses = [t for t in recent_trades if t['result'] == 'loss']
        
        self.win_rate = len(wins) / len(recent_trades) if recent_trades else 0.5
        self.avg_win = abs(sum(t['pnl_pct'] for t in wins) / len(wins)) if wins else 0.02
        self.avg_loss = abs(sum(t['pnl_pct'] for t in losses) / len(losses)) if losses else 0.01
        
        logger.info(f"Updated stats: Win rate={self.win_rate:.1%}, Avg win={self.avg_win:.2%}, Avg loss={self.avg_loss:.2%}")
    
    async def monitor_positions(self) -> Dict[str, Any]:
        """
        Comprehensive position monitoring with auto-management
        
        Returns:
            Risk report with alerts and actions taken
        """
        alerts = []
        actions = []
        
        try:
            # Get positions
            positions = await self.order_manager.get_positions()
            
            # Use cached account info (refresh every 30 seconds to avoid rate limits)
            now = datetime.now()
            if (now - self.account_cache_time).total_seconds() >= 60 or self.account_cache is None:
                self.account_cache = await self.order_manager.get_account_info()
                self.account_cache_time = now
            
            account_info = self.account_cache
            
            # Parse account balance from nested structure
            current_balance = 0.0
            if isinstance(account_info, dict):
                if 'accounts' in account_info and len(account_info['accounts']) > 0:
                    acc_data = account_info['accounts'][0]
                    current_balance = float(acc_data.get('collateral', 0))
                elif 'collateral' in account_info:
                    current_balance = float(account_info.get('collateral', 0))
            
            # Update daily tracking
            if self.daily_start_balance is None:
                self.daily_start_balance = current_balance
                self.daily_high_balance = current_balance
            
            # Track maximum drawdown
            if current_balance > self.daily_high_balance:
                self.daily_high_balance = current_balance
            
            if self.daily_high_balance > 0:
                daily_drawdown = (self.daily_high_balance - current_balance) / self.daily_high_balance
                self.max_drawdown_today = max(self.max_drawdown_today, daily_drawdown)
            
            for position in positions:
                if not position.is_open:
                    continue
                
                market_id = position.market_id
                current_pnl_pct = position.pnl_percentage
                
                # Get symbol from settings
                symbol = settings.trading_symbol
                
                self.logger.info(f"Position {symbol}: PnL {current_pnl_pct:+.2f}%")
                
                # Check for scaled profit exits using profit_manager
                from profit_manager import profit_manager
                
                # Create trade_id (use market_id + symbol for lookup)
                trade_id = f"{market_id}_{symbol}"
                
                exit_plan = profit_manager.get_plan(trade_id)
                if exit_plan:
                    triggered_levels = profit_manager.check_profit_levels(trade_id, current_pnl_pct)
                    
                    for level in triggered_levels:
                        self.logger.info(f"🎯 Level {level.level_num} triggered: {current_pnl_pct:.2f}% >= {level.trigger_percent:.2f}%")
                        side = "sell" if position.is_long else "buy"
                        
                        try:
                            success = await self.order_manager.place_market_order(
                                side=side,
                                size=level.size,
                                market_id=market_id
                            )
                            
                            if success:
                                profit_manager.mark_level_filled(trade_id, level.level_num, position.mark_price)
                                actions.append(f"Executed Level {level.level_num} exit on {symbol}: {level.size:.4f} @ {level.trigger_percent:.1f}%")
                                self.logger.info(f"✅ Level {level.level_num} executed successfully")
                            else:
                                self.logger.error(f"❌ Failed to execute Level {level.level_num}")
                        except Exception as e:
                            self.logger.error(f"Error executing Level {level.level_num}: {e}")
                
                # =====================================================
                # INTELLIGENT EARLY EXIT DETECTION (Before Stop Loss)
                # =====================================================
                try:
                    trade_id = f"{symbol}_{self.trade_count if hasattr(self, 'trade_count') else position.id}"
                    
                    # Check if setup is still valid
                    should_exit, exit_reason = self.trade_validator.should_exit_early(
                        trade_id=trade_id,
                        current_price=position.mark_price,
                        current_pnl_pct=current_pnl_pct,
                        market_data=self.market_data
                    )
                    
                    if should_exit:
                        self.logger.warning(f"⚠️ EARLY EXIT TRIGGERED: {symbol} - {exit_reason}")
                        self.logger.warning(f"   Current PnL: {current_pnl_pct:.2f}% (exiting before -2% stop loss)")
                        
                        side = "sell" if position.is_long else "buy"
                        try:
                            success = await self.order_manager.place_market_order(
                                side=side,
                                size=abs(position.size),
                                market_id=market_id
                            )
                            
                            if success:
                                profit_manager.remove_plan(trade_id)
                                self.trade_validator.remove_trade(trade_id)
                                actions.append(f"Early exit on {symbol}: {current_pnl_pct:.2f}% - {exit_reason}")
                                self.logger.info(f"✅ Early exit executed - saved capital!")
                            else:
                                self.logger.error(f"❌ Failed to execute early exit")
                        except Exception as e:
                            self.logger.error(f"Error executing early exit: {e}")
                        
                        continue  # Skip further checks if early exited
                
                except Exception as e:
                    self.logger.debug(f"Early exit check error: {e}")
                
                # Check stop-loss (always monitor)
                if current_pnl_pct <= -settings.stop_loss_percent:
                    self.logger.warning(f"🛑 STOP-LOSS: {symbol} PnL {current_pnl_pct:.2f}% <= -{settings.stop_loss_percent:.2f}%")
                    
                    side = "sell" if position.is_long else "buy"
                    try:
                        success = await self.order_manager.place_market_order(
                            side=side,
                            size=abs(position.size),
                            market_id=market_id
                        )
                        
                        if success:
                            profit_manager.remove_plan(trade_id)
                            actions.append(f"Stop-loss executed on {symbol}: -{settings.stop_loss_percent:.1f}%")
                            self.logger.info(f"✅ Stop-loss executed")
                        else:
                            self.logger.error(f"❌ Failed to execute stop-loss")
                    except Exception as e:
                        self.logger.error(f"Error executing stop-loss: {e}")
                
                # Enhanced liquidation risk monitoring
                if position.liquidation_price:
                    # Use mark_price (current price from API) not current_price
                    distance_pct = abs((position.mark_price - position.liquidation_price) / position.mark_price) * 100
                    
                    # CRITICAL: Within 10% of liquidation - AUTO REDUCE
                    if distance_pct < 10.0:
                        alert = f"🚨 CRITICAL LIQUIDATION RISK: {symbol} {distance_pct:.1f}% from liquidation! AUTO-REDUCING POSITION"
                        alerts.append(alert)
                        logger.error(alert)
                        
                        # Reduce position by 50%
                        reduce_size = abs(position.size) * 0.5
                        side = "sell" if position.is_long else "buy"
                        try:
                            await self.order_manager.place_market_order(
                                side=side,
                                size=reduce_size,
                                market_id=position.market_id
                            )
                            actions.append(f"Auto-reduced {symbol} by 50% (liquidation protection)")
                            logger.warning(f"✅ Reduced {symbol} position by 50%")
                        except Exception as e:
                            logger.error(f"Failed to reduce position: {e}")
                    
                    # WARNING: Within 15% of liquidation
                    elif distance_pct < 15.0:
                        alert = f"⚠️ HIGH LIQUIDATION RISK: {symbol} {distance_pct:.1f}% from liquidation!"
                        alerts.append(alert)
                        logger.warning(alert)
                    
                    # INFO: Within 20% of liquidation
                    elif distance_pct < 20.0:
                        alert = f"⚡ Liquidation distance: {symbol} {distance_pct:.1f}% (monitor closely)"
                        alerts.append(alert)
                        logger.info(alert)
            
            portfolio_heat = await self.calculate_portfolio_heat()
            
            return {
                "timestamp": datetime.now(),
                "positions_count": len(positions),
                "alerts": alerts,
                "actions": actions,
                "portfolio_heat": portfolio_heat,
                "daily_drawdown": daily_drawdown,
                "max_drawdown_today": self.max_drawdown_today,
                "win_rate": self.win_rate,
                "kelly_fraction": self.calculate_kelly_size()
            }
            
        except Exception as e:
            logger.error(f"Error monitoring positions: {e}")
            return {
                "timestamp": datetime.now(),
                "positions_count": 0,
                "alerts": [f"Error: {e}"],
                "actions": []
            }
