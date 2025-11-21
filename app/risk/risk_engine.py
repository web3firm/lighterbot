"""
Risk Engine - Validates all trades against risk rules
Position sizing, leverage limits, correlation checks
"""

import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Risk engine that validates all trades against risk management rules
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize risk engine
        
        Args:
            config: Configuration dict
        """
        self.config = config or {}
        
        # Risk limits
        self.max_position_size_pct = Decimal(str(self.config.get('max_position_size_pct', 70.0)))
        self.max_positions = self.config.get('max_positions', 2)
        self.max_leverage = self.config.get('max_leverage', 5)
        self.max_daily_loss_pct = Decimal(str(self.config.get('max_daily_loss_pct', 5.0)))
        
        # Position tracking
        self.open_positions: List[Dict[str, Any]] = []
        self.daily_pnl = Decimal('0')
        
        logger.info(f"🛡️  Risk Engine initialized")
        logger.info(f"   Max position size: {self.max_position_size_pct}%")
        logger.info(f"   Max positions: {self.max_positions}")
        logger.info(f"   Max leverage: {self.max_leverage}x")
        logger.info(f"   Max daily loss: {self.max_daily_loss_pct}%")
    
    def validate_signal(self, signal: Dict[str, Any], 
                       account_state: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate trading signal against all risk rules
        
        Args:
            signal: Trading signal
            account_state: Current account state
            
        Returns:
            (is_valid, reason) tuple
        """
        # Check 1: Max positions
        if len(self.open_positions) >= self.max_positions:
            return False, f"Max positions limit reached ({self.max_positions})"
        
        # Check 2: Leverage limit
        leverage = signal.get('leverage', 1)
        if leverage > self.max_leverage:
            return False, f"Leverage {leverage}x exceeds max {self.max_leverage}x"
        
        # Check 3: Position size (margin percentage, not notional)
        account_value = Decimal(str(account_state.get('account_value', 0)))
        entry_price = Decimal(str(signal.get('entry_price', 0)))
        size = Decimal(str(signal.get('size', 0)))
        leverage = Decimal(str(signal.get('leverage', 1)))
        
        if account_value > 0 and entry_price > 0 and leverage > 0:
            # Calculate margin used (notional / leverage)
            position_notional = size * entry_price
            margin_used = position_notional / leverage
            margin_pct = (margin_used / account_value) * Decimal('100')
            
            if margin_pct > self.max_position_size_pct + Decimal('0.1'):  # Allow small rounding
                return False, f"Position size {margin_pct:.1f}% exceeds max {self.max_position_size_pct}%"
        
        # Check 4: Daily loss limit
        if self.daily_pnl < 0:
            daily_loss_pct = abs(self.daily_pnl / account_value * Decimal('100'))
            if daily_loss_pct >= self.max_daily_loss_pct:
                return False, f"Daily loss limit reached ({daily_loss_pct:.2f}%)"
        
        # Check 5: Signal confidence
        confidence = signal.get('confidence', 0)
        if confidence < 0.5:
            return False, f"Signal confidence too low ({confidence:.2%})"
        
        # All checks passed
        logger.info(f"✅ Risk validation passed")
        return True, "OK"
    
    def add_position(self, position: Dict[str, Any]):
        """Add open position"""
        self.open_positions.append(position)
        logger.info(f"📊 Position added: {position.get('symbol')} {position.get('side')}")
        logger.info(f"   Open positions: {len(self.open_positions)}/{self.max_positions}")
    
    def remove_position(self, symbol: str):
        """Remove closed position"""
        self.open_positions = [p for p in self.open_positions if p.get('symbol') != symbol]
        logger.info(f"📊 Position removed: {symbol}")
        logger.info(f"   Open positions: {len(self.open_positions)}/{self.max_positions}")
    
    def update_daily_pnl(self, pnl: Decimal):
        """Update daily PnL"""
        self.daily_pnl = pnl
    
    def reset_daily_stats(self):
        """Reset daily statistics"""
        logger.info("🔄 Resetting daily stats")
        self.daily_pnl = Decimal('0')
    
    def get_status(self) -> Dict[str, Any]:
        """Get risk engine status"""
        return {
            'max_position_size_pct': float(self.max_position_size_pct),
            'max_positions': self.max_positions,
            'max_leverage': self.max_leverage,
            'max_daily_loss_pct': float(self.max_daily_loss_pct),
            'open_positions': len(self.open_positions),
            'daily_pnl': float(self.daily_pnl)
        }
