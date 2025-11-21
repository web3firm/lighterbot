"""
Risk Manager - Consolidated risk management
Coordinates kill switch, drawdown monitor, and risk engine
"""

import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timezone

from app.risk.kill_switch import KillSwitch
from app.risk.drawdown_monitor import DrawdownMonitor
from app.risk.risk_engine import RiskEngine

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Consolidated risk management system
    Coordinates kill switch, drawdown monitoring, and trade validation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize risk manager
        
        Args:
            config: Configuration dict
        """
        self.config = config or {}
        
        # Initialize components
        self.kill_switch = KillSwitch(self.config.get('kill_switch', {}))
        self.drawdown_monitor = DrawdownMonitor(self.config.get('drawdown', {}))
        self.risk_engine = RiskEngine(self.config.get('risk_limits', {}))
        
        # State
        self.session_start_time = datetime.now(timezone.utc)
        self.last_equity_update = datetime.now(timezone.utc)
        
        logger.info("🛡️  Risk Manager initialized")
        logger.info(f"   Session start: {self.session_start_time.isoformat()}")
    
    def initialize_session(self, starting_equity: Decimal):
        """
        Initialize trading session
        
        Args:
            starting_equity: Starting equity for session
        """
        self.kill_switch.set_session_start_equity(starting_equity)
        self.drawdown_monitor.update(starting_equity)
        
        logger.info(f"📊 Risk session initialized with ${starting_equity:.2f}")
    
    def check_risk_state(self, current_equity: Decimal, has_open_positions: bool = False) -> tuple[bool, str]:
        """
        Check overall risk state
        
        Args:
            current_equity: Current account equity
            has_open_positions: Whether there are open positions
            
        Returns:
            (can_trade, reason) tuple
        """
        # Check kill switch (only when no positions to avoid margin-in-use false triggers)
        if self.kill_switch.check(current_equity, has_open_positions):
            return False, "Kill switch triggered"
        
        # Update drawdown
        self.drawdown_monitor.update(current_equity)
        
        # Check if paused by drawdown
        if self.drawdown_monitor.is_paused():
            return False, "Trading paused due to critical drawdown"
        
        # Update timestamp
        self.last_equity_update = datetime.now(timezone.utc)
        
        return True, "OK"
    
    def validate_signal(self, signal: Dict[str, Any],
                       account_state: Dict[str, Any]) -> tuple[bool, str]:
        """
        Validate trading signal
        
        Args:
            signal: Trading signal
            account_state: Current account state
            
        Returns:
            (is_valid, reason) tuple
        """
        # Check if kill switch is active
        if self.kill_switch.is_triggered():
            return False, "Kill switch active"
        
        # Check if drawdown paused
        if self.drawdown_monitor.is_paused():
            return False, "Drawdown pause active"
        
        # Validate with risk engine
        is_valid, reason = self.risk_engine.validate_signal(signal, account_state)
        
        if not is_valid:
            logger.warning(f"⚠️  Signal rejected: {reason}")
            return False, reason
        
        return True, "OK"
    
    def on_position_opened(self, position: Dict[str, Any]):
        """Handle position opened event"""
        self.risk_engine.add_position(position)
        logger.info(f"✅ Position opened: {position.get('symbol')} {position.get('side')}")
    
    def on_position_closed(self, symbol: str, pnl: Decimal):
        """Handle position closed event"""
        self.risk_engine.remove_position(symbol)
        logger.info(f"✅ Position closed: {symbol} | PnL: ${pnl:.2f}")
    
    def update_daily_pnl(self, pnl: Decimal):
        """Update daily PnL"""
        self.risk_engine.update_daily_pnl(pnl)
    
    def reset_daily_stats(self):
        """Reset daily statistics (call at session start)"""
        self.risk_engine.reset_daily_stats()
        logger.info("🔄 Daily risk stats reset")
    
    def get_full_status(self) -> Dict[str, Any]:
        """Get complete risk status"""
        return {
            'session_start_time': self.session_start_time.isoformat(),
            'last_equity_update': self.last_equity_update.isoformat(),
            'kill_switch': self.kill_switch.get_status(),
            'drawdown': self.drawdown_monitor.get_status(),
            'risk_engine': self.risk_engine.get_status(),
            'can_trade': not (self.kill_switch.is_triggered() or self.drawdown_monitor.is_paused())
        }
    
    def emergency_shutdown(self):
        """Emergency shutdown - close all positions"""
        logger.critical("🚨 EMERGENCY SHUTDOWN INITIATED")
        logger.critical(f"   Open positions: {len(self.risk_engine.open_positions)}")
        logger.critical(f"   Kill switch: {self.kill_switch.is_triggered()}")
        logger.critical(f"   Drawdown paused: {self.drawdown_monitor.is_paused()}")
        
        # Trigger kill switch if not already triggered
        if not self.kill_switch.is_triggered():
            current_equity = self.kill_switch.session_start_equity or Decimal('0')
            self.kill_switch._trigger(Decimal('100'), Decimal('0'))  # Force trigger
        
        return self.risk_engine.open_positions


if __name__ == "__main__":
    # Test risk manager
    import asyncio
    
    async def test():
        config = {
            'kill_switch': {'daily_loss_trigger_pct': 5.0},
            'drawdown': {'warning_threshold_pct': 5.0, 'critical_threshold_pct': 10.0},
            'risk_limits': {'max_positions': 2, 'max_leverage': 5}
        }
        
        manager = RiskManager(config)
        manager.initialize_session(Decimal('1000'))
        
        # Test equity update
        can_trade, reason = manager.check_risk_state(Decimal('980'))
        print(f"Can trade: {can_trade} - {reason}")
        
        # Test signal validation
        signal = {
            'symbol': 'BTC-USD',
            'side': 'buy',
            'leverage': 5,
            'size': 0.01,
            'entry_price': 50000,
            'confidence': 0.7
        }
        
        account_state = {'account_value': 980}
        
        is_valid, reason = manager.validate_signal(signal, account_state)
        print(f"Signal valid: {is_valid} - {reason}")
        
        # Get status
        status = manager.get_full_status()
        print(f"Status: {status}")
    
    asyncio.run(test())
