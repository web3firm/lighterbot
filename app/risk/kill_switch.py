"""
Kill Switch - Emergency stop at -5% daily loss
Automatically stops trading when loss threshold exceeded
"""

import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class KillSwitch:
    """
    Kill switch that stops trading at -5% daily loss threshold
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize kill switch
        
        Args:
            config: Configuration dict
        """
        self.config = config or {}
        
        # Configuration - use MAX_DAILY_LOSS_PCT from .env (default 10%)
        self.daily_loss_trigger_pct = Decimal(str(self.config.get('daily_loss_trigger_pct', 10.0)))
        
        # State
        self.triggered = False
        self.triggered_at: Optional[datetime] = None
        self.trigger_reason: Optional[str] = None
        self.session_start_equity: Optional[Decimal] = None
        
        logger.info(f"🚨 Kill Switch initialized")
        logger.info(f"   Trigger: -{self.daily_loss_trigger_pct}% daily loss")
    
    def set_session_start_equity(self, equity: Decimal):
        """Set session start equity"""
        self.session_start_equity = equity
        logger.info(f"📊 Session start equity: ${equity:.2f}")
    
    def check(self, current_equity: Decimal, has_open_positions: bool = False) -> bool:
        """
        Check if kill switch should be triggered
        
        Args:
            current_equity: Current account equity
            has_open_positions: Whether there are open positions (skips check if True)
            
        Returns:
            True if triggered, False otherwise
        """
        if self.triggered:
            return True
        
        if not self.session_start_equity:
            return False
        
        # Don't check equity if positions are open (margin-in-use reduces equity temporarily)
        if has_open_positions:
            return False
        
        # Calculate daily loss
        loss = self.session_start_equity - current_equity
        loss_pct = (loss / self.session_start_equity) * Decimal('100')
        
        # Check if loss exceeds threshold
        if loss_pct >= self.daily_loss_trigger_pct:
            self._trigger(loss_pct, current_equity)
            return True
        
        return False
    
    def _trigger(self, loss_pct: Decimal, current_equity: Decimal):
        """Trigger kill switch"""
        self.triggered = True
        self.triggered_at = datetime.now(timezone.utc)
        self.trigger_reason = f"Daily loss of {loss_pct:.2f}% exceeded {self.daily_loss_trigger_pct}% threshold"
        
        logger.critical("🚨" * 20)
        logger.critical("🚨 KILL SWITCH TRIGGERED!")
        logger.critical(f"   Reason: {self.trigger_reason}")
        logger.critical(f"   Session Start: ${self.session_start_equity:.2f}")
        logger.critical(f"   Current Equity: ${current_equity:.2f}")
        logger.critical(f"   Loss: ${self.session_start_equity - current_equity:.2f} ({loss_pct:.2f}%)")
        logger.critical(f"   Timestamp: {self.triggered_at.isoformat()}")
        logger.critical("🚨 ALL TRADING STOPPED!")
        logger.critical("🚨" * 20)
    
    def is_triggered(self) -> bool:
        """Check if kill switch is triggered"""
        return self.triggered
    
    def reset(self):
        """Reset kill switch (use with caution)"""
        logger.warning("⚠️  Resetting kill switch")
        self.triggered = False
        self.triggered_at = None
        self.trigger_reason = None
    
    def get_status(self) -> Dict[str, Any]:
        """Get kill switch status"""
        return {
            'triggered': self.triggered,
            'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
            'trigger_reason': self.trigger_reason,
            'daily_loss_trigger_pct': float(self.daily_loss_trigger_pct),
            'session_start_equity': float(self.session_start_equity) if self.session_start_equity else None
        }
