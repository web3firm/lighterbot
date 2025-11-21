"""
Drawdown Monitor - Track drawdown from peak equity
Monitors 10% max drawdown threshold
"""

import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DrawdownMonitor:
    """
    Monitors drawdown from peak equity
    Warns at thresholds and can pause trading at critical levels
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize drawdown monitor
        
        Args:
            config: Configuration dict
        """
        self.config = config or {}
        
        # Configuration
        self.warning_threshold_pct = Decimal(str(self.config.get('warning_threshold_pct', 5.0)))
        self.critical_threshold_pct = Decimal(str(self.config.get('critical_threshold_pct', 10.0)))
        self.auto_pause_enabled = self.config.get('auto_pause_enabled', True)
        
        # State
        self.peak_equity: Optional[Decimal] = None
        self.peak_equity_time: Optional[datetime] = None
        self.current_drawdown_pct = Decimal('0')
        self.max_drawdown_pct = Decimal('0')
        self.warning_triggered = False
        self.critical_triggered = False
        self.paused = False
        
        logger.info(f"📉 Drawdown Monitor initialized")
        logger.info(f"   Warning: {self.warning_threshold_pct}%")
        logger.info(f"   Critical: {self.critical_threshold_pct}%")
        logger.info(f"   Auto-pause: {self.auto_pause_enabled}")
    
    def update(self, current_equity: Decimal):
        """
        Update drawdown calculation
        
        Args:
            current_equity: Current account equity
        """
        # Update peak equity
        if self.peak_equity is None or current_equity > self.peak_equity:
            self.peak_equity = current_equity
            self.peak_equity_time = datetime.now(timezone.utc)
            self.warning_triggered = False
            self.critical_triggered = False
            
            logger.info(f"🏔️  New peak equity: ${current_equity:.2f}")
        
        # Calculate current drawdown
        if self.peak_equity and self.peak_equity > 0:
            drawdown = self.peak_equity - current_equity
            self.current_drawdown_pct = (drawdown / self.peak_equity) * Decimal('100')
            
            # Update max drawdown
            if self.current_drawdown_pct > self.max_drawdown_pct:
                self.max_drawdown_pct = self.current_drawdown_pct
            
            # Check thresholds
            self._check_thresholds()
    
    def _check_thresholds(self):
        """Check drawdown thresholds"""
        # Warning threshold
        if not self.warning_triggered and self.current_drawdown_pct >= self.warning_threshold_pct:
            self.warning_triggered = True
            logger.warning(f"⚠️  DRAWDOWN WARNING!")
            logger.warning(f"   Current: {self.current_drawdown_pct:.2f}%")
            logger.warning(f"   Threshold: {self.warning_threshold_pct}%")
            logger.warning(f"   Peak: ${self.peak_equity:.2f}")
        
        # Critical threshold
        if not self.critical_triggered and self.current_drawdown_pct >= self.critical_threshold_pct:
            self.critical_triggered = True
            logger.error(f"🚨 DRAWDOWN CRITICAL!")
            logger.error(f"   Current: {self.current_drawdown_pct:.2f}%")
            logger.error(f"   Threshold: {self.critical_threshold_pct}%")
            logger.error(f"   Peak: ${self.peak_equity:.2f}")
            
            if self.auto_pause_enabled:
                self.paused = True
                logger.error(f"⏸️  TRADING PAUSED DUE TO CRITICAL DRAWDOWN")
    
    def is_critical(self) -> bool:
        """Check if at critical drawdown"""
        return self.critical_triggered
    
    def is_paused(self) -> bool:
        """Check if trading is paused"""
        return self.paused
    
    def resume(self):
        """Resume trading (manual override)"""
        if self.paused:
            logger.warning("▶️  Resuming trading (manual override)")
            self.paused = False
    
    def get_status(self) -> Dict[str, Any]:
        """Get drawdown status"""
        return {
            'peak_equity': float(self.peak_equity) if self.peak_equity else None,
            'peak_equity_time': self.peak_equity_time.isoformat() if self.peak_equity_time else None,
            'current_drawdown_pct': float(self.current_drawdown_pct),
            'max_drawdown_pct': float(self.max_drawdown_pct),
            'warning_threshold_pct': float(self.warning_threshold_pct),
            'critical_threshold_pct': float(self.critical_threshold_pct),
            'warning_triggered': self.warning_triggered,
            'critical_triggered': self.critical_triggered,
            'paused': self.paused
        }
