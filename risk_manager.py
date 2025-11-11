"""
Advanced Risk Management System
"""
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import math

from order_manager import OrderManager
from market_data import MarketData
from config import settings
from logger import logger


@dataclass
class RiskLimits:
    """Risk limit configuration"""
    max_position_size: float
    max_leverage: int
    max_daily_drawdown: float
    liquidation_threshold: float
    max_open_orders: int
    min_margin_ratio: float = 0.2
    max_portfolio_heat: float = 0.3  # Max 30% of portfolio at risk
    max_correlation_exposure: float = 0.5  # Max 50% in correlated positions


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
    
    def calculate_position_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss_price: float = None,  # Now optional
        risk_per_trade: float = 0.02,  # Legacy parameter, not used in new method
        market_id: Optional[int] = None
    ) -> float:
        """
        Calculate position size as percentage of account balance with leverage
        
        New method: position_size = (account_balance × position_percent × leverage) / entry_price
        
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
        position_percent = settings.position_size_percent / 100.0  # e.g., 0.20 for 20%
        leverage = settings.leverage  # e.g., 3x
        
        # Calculate position size in USD
        position_value_usd = account_balance * position_percent * leverage
        
        # Convert to coins
        position_size_coins = position_value_usd / entry_price
        
        # Get minimum order size from API metadata
        if market_id:
            min_size = market_metadata.get_min_order_size(market_id)
        else:
            min_size = 0.001  # Fallback
        
        # Ensure minimum viable size
        if position_size_coins < min_size:
            position_size_coins = min_size
            self.logger.warning(
                f"Calculated position {position_size_coins:.6f} below minimum {min_size:.6f}, "
                f"using minimum instead"
            )
        
        # Cap at max position size (safety check)
        final_size = min(position_size_coins, self.limits.max_position_size)
        
        self.logger.info(
            f"Position sizing: ${account_balance:.2f} × {settings.position_size_percent}% × {leverage}x "
            f"= ${position_value_usd:.2f} = {final_size:.6f} coins @ ${entry_price:.2f}"
        )
        
        return final_size
    
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
        Advanced risk check with position sizing
        
        Returns:
            (approved, reason, adjusted_size) tuple
        """
        try:
            # Get account info
            account_info = await self.order_manager.get_account_info()
            
            # Parse account balance from nested structure
            account_balance = 0.0
            if isinstance(account_info, dict):
                if 'accounts' in account_info and len(account_info['accounts']) > 0:
                    acc_data = account_info['accounts'][0]
                    account_balance = float(acc_data.get('collateral', 0))
                elif 'collateral' in account_info:
                    account_balance = float(account_info.get('collateral', 0))
            
            if account_balance == 0:
                return False, "Account balance is zero", 0.0
            
            # Calculate risk-adjusted position size
            if stop_loss:
                optimal_size = self.calculate_position_size(
                    account_balance=account_balance,
                    entry_price=price,
                    stop_loss_price=stop_loss,
                    market_id=market_id
                )
                
                if size > optimal_size * 1.5:  # Allow 50% buffer
                    logger.warning(f"Requested size {size} exceeds optimal {optimal_size:.4f}, adjusting")
                    size = optimal_size
            
            # Check position size limit
            if size > self.limits.max_position_size:
                return False, f"Order size {size} exceeds max {self.limits.max_position_size}", 0.0
            
            # Check portfolio heat (total risk exposure)
            portfolio_heat = await self.calculate_portfolio_heat()
            order_heat = (size * price) / account_balance
            
            if portfolio_heat + order_heat > self.limits.max_portfolio_heat:
                return False, f"Portfolio heat {(portfolio_heat + order_heat):.1%} exceeds max {self.limits.max_portfolio_heat:.1%}", 0.0
            
            # Check daily drawdown
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
        Calculate total portfolio heat (risk exposure)
        
        Returns:
            Portfolio heat as fraction (0-1)
        """
        try:
            positions = await self.order_manager.get_positions()
            account_info = await self.order_manager.get_account_info()
            
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
            
            total_exposure = sum(abs(p.size * p.current_price) for p in positions)
            return total_exposure / account_balance
            
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
                return False
            
            # Check stop-loss
            if position.pnl_percentage <= stop_loss_pct:
                logger.warning(f"Stop-loss triggered for market {market_id}: PnL {position.pnl_percentage:.2f}%")
                
                # Close position
                side = "sell" if position.is_long else "buy"
                await self.order_manager.place_market_order(
                    side=side,
                    size=abs(position.size),
                    market_id=market_id
                )
                
                # Track trade result
                self.trade_history.append({
                    'result': 'loss',
                    'pnl_pct': position.pnl_percentage,
                    'timestamp': datetime.now()
                })
                self.update_statistics()
                
                return True
            
            # Check take-profit
            if position.pnl_percentage >= take_profit_pct:
                logger.info(f"Take-profit triggered for market {market_id}: PnL {position.pnl_percentage:.2f}%")
                
                # Close position
                side = "sell" if position.is_long else "buy"
                await self.order_manager.place_market_order(
                    side=side,
                    size=abs(position.size),
                    market_id=market_id
                )
                
                # Track trade result
                self.trade_history.append({
                    'result': 'win',
                    'pnl_pct': position.pnl_percentage,
                    'timestamp': datetime.now()
                })
                self.update_statistics()
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in auto stop-loss/take-profit: {e}")
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
            account_info = await self.order_manager.get_account_info()
            
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
                # Auto stop-loss/take-profit
                closed = await self.auto_stop_loss_take_profit(
                    position.market_id,
                    position
                )
                
                if closed:
                    actions.append(f"Auto-closed position on market {position.market_id}")
                
                # Check liquidation risk
                if position.liquidation_price:
                    distance_pct = abs((position.current_price - position.liquidation_price) / position.current_price) * 100
                    
                    if distance_pct < self.limits.liquidation_threshold * 100:
                        alert = f"⚠️ LIQUIDATION RISK: Market {position.symbol} within {distance_pct:.1f}% of liquidation!"
                        alerts.append(alert)
                        logger.error(alert)
            
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
