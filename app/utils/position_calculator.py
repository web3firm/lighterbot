"""
Position Calculator - Calculate position sizes, leverage, and risk metrics
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PositionCalculator:
    """
    Calculate position sizes, leverage, and risk metrics
    """
    
    def __init__(self):
        """Initialize position calculator"""
        logger.info("✅ Position calculator initialized")
    
    def calculate_position_size(self, account_value: Decimal, position_size_pct: Decimal,
                               leverage: int, price: Decimal) -> Decimal:
        """
        Calculate position size
        
        Args:
            account_value: Account value in USD
            position_size_pct: Position size as percentage (0-100)
            leverage: Leverage multiplier
            price: Entry price
            
        Returns:
            Position size in base currency
        """
        # Capital allocated to this position
        capital = account_value * (position_size_pct / Decimal('100'))
        
        # Notional value with leverage
        notional_value = capital * Decimal(str(leverage))
        
        # Position size
        position_size = notional_value / price
        
        return position_size
    
    def calculate_pnl(self, entry_price: Decimal, exit_price: Decimal,
                     size: Decimal, side: str, leverage: int) -> tuple[Decimal, Decimal]:
        """
        Calculate PnL and PnL percentage
        
        Args:
            entry_price: Entry price
            exit_price: Exit price
            size: Position size
            side: 'buy' (long) or 'sell' (short)
            leverage: Leverage multiplier
            
        Returns:
            (pnl_usd, pnl_pct) tuple
        """
        if side == 'buy':
            # Long position
            price_change_pct = ((exit_price - entry_price) / entry_price) * Decimal('100')
        else:
            # Short position
            price_change_pct = ((entry_price - exit_price) / entry_price) * Decimal('100')
        
        # PnL percentage (leveraged)
        pnl_pct = price_change_pct * Decimal(str(leverage))
        
        # PnL in USD
        notional_value = entry_price * size
        pnl_usd = (notional_value * pnl_pct) / Decimal('100')
        
        return pnl_usd, pnl_pct
    
    def calculate_liquidation_price(self, entry_price: Decimal, side: str,
                                   leverage: int, maintenance_margin_rate: Decimal = Decimal('0.005')) -> Decimal:
        """
        Calculate liquidation price
        
        Args:
            entry_price: Entry price
            side: 'buy' (long) or 'sell' (short)
            leverage: Leverage multiplier
            maintenance_margin_rate: Maintenance margin rate (default 0.5%)
            
        Returns:
            Liquidation price
        """
        if side == 'buy':
            # Long position
            liquidation_pct = (Decimal('1') / Decimal(str(leverage))) - maintenance_margin_rate
            liquidation_price = entry_price * (Decimal('1') - liquidation_pct)
        else:
            # Short position
            liquidation_pct = (Decimal('1') / Decimal(str(leverage))) - maintenance_margin_rate
            liquidation_price = entry_price * (Decimal('1') + liquidation_pct)
        
        return liquidation_price
    
    def calculate_stop_loss_price(self, entry_price: Decimal, side: str,
                                  sl_pct: Decimal, leverage: int) -> Decimal:
        """
        Calculate stop-loss price from PnL percentage
        
        Args:
            entry_price: Entry price
            side: 'buy' or 'sell'
            sl_pct: Stop-loss PnL percentage (positive number)
            leverage: Leverage multiplier
            
        Returns:
            Stop-loss price
        """
        # Convert PnL% to price change%
        price_change_pct = sl_pct / Decimal(str(leverage))
        
        if side == 'buy':
            # Long: SL below entry
            sl_price = entry_price * (Decimal('1') - price_change_pct / Decimal('100'))
        else:
            # Short: SL above entry
            sl_price = entry_price * (Decimal('1') + price_change_pct / Decimal('100'))
        
        return sl_price
    
    def calculate_take_profit_price(self, entry_price: Decimal, side: str,
                                    tp_pct: Decimal, leverage: int) -> Decimal:
        """
        Calculate take-profit price from PnL percentage
        
        Args:
            entry_price: Entry price
            side: 'buy' or 'sell'
            tp_pct: Take-profit PnL percentage (positive number)
            leverage: Leverage multiplier
            
        Returns:
            Take-profit price
        """
        # Convert PnL% to price change%
        price_change_pct = tp_pct / Decimal(str(leverage))
        
        if side == 'buy':
            # Long: TP above entry
            tp_price = entry_price * (Decimal('1') + price_change_pct / Decimal('100'))
        else:
            # Short: TP below entry
            tp_price = entry_price * (Decimal('1') - price_change_pct / Decimal('100'))
        
        return tp_price
    
    def round_price(self, price: Decimal, decimals: Optional[int] = None) -> Decimal:
        """
        Round price to appropriate decimals
        
        Args:
            price: Price to round
            decimals: Number of decimals (auto-detect if None)
            
        Returns:
            Rounded price
        """
        if decimals is None:
            # Auto-detect decimals based on price magnitude
            price_val = float(price)
            if price_val >= 100:
                decimals = 2
            elif price_val >= 10:
                decimals = 3
            elif price_val >= 1:
                decimals = 4
            else:
                decimals = 6
        
        return round(price, decimals)
    
    def calculate_risk_reward_ratio(self, entry_price: Decimal, sl_price: Decimal,
                                    tp_price: Decimal, side: str) -> Decimal:
        """
        Calculate risk-reward ratio
        
        Args:
            entry_price: Entry price
            sl_price: Stop-loss price
            tp_price: Take-profit price
            side: 'buy' or 'sell'
            
        Returns:
            Risk-reward ratio (e.g., 3.0 for 3:1)
        """
        if side == 'buy':
            risk = entry_price - sl_price
            reward = tp_price - entry_price
        else:
            risk = sl_price - entry_price
            reward = entry_price - tp_price
        
        if risk <= 0:
            return Decimal('0')
        
        return reward / risk


# Global calculator instance
_calculator: Optional[PositionCalculator] = None


def get_calculator() -> PositionCalculator:
    """Get or create global calculator"""
    global _calculator
    if _calculator is None:
        _calculator = PositionCalculator()
    return _calculator


if __name__ == "__main__":
    # Test position calculator
    calc = get_calculator()
    
    # Test position size
    account_value = Decimal('1000')
    position_size_pct = Decimal('50')
    leverage = 5
    price = Decimal('50000')
    
    size = calc.calculate_position_size(account_value, position_size_pct, leverage, price)
    print(f"Position size: {size} BTC")
    
    # Test PnL
    entry = Decimal('50000')
    exit = Decimal('51000')
    pnl_usd, pnl_pct = calc.calculate_pnl(entry, exit, size, 'buy', leverage)
    print(f"PnL: ${pnl_usd:.2f} ({pnl_pct:.2f}%)")
    
    # Test stop-loss price
    sl_price = calc.calculate_stop_loss_price(entry, 'buy', Decimal('5'), leverage)
    print(f"SL price: ${sl_price:.2f}")
    
    # Test take-profit price
    tp_price = calc.calculate_take_profit_price(entry, 'buy', Decimal('15'), leverage)
    print(f"TP price: ${tp_price:.2f}")
    
    # Test risk-reward ratio
    rr = calc.calculate_risk_reward_ratio(entry, sl_price, tp_price, 'buy')
    print(f"Risk-Reward: 1:{rr:.1f}")
