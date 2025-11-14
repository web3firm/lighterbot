"""
Drawdown Protection and Recovery Mode

Reduces position size after consecutive losses to prevent revenge trading.
Gradually recovers size as wins accumulate.
"""

from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from logger import get_logger

logger = get_logger()


@dataclass
class DrawdownState:
    """Current drawdown protection state"""
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    peak_balance: float = 0.0
    current_drawdown_pct: float = 0.0
    recovery_mode: bool = False
    size_multiplier: float = 1.0
    last_reset: datetime = None


class DrawdownProtection:
    """
    Protect capital during losing streaks
    
    Rules:
    - 3 losses in a row: Reduce size to 50%
    - 5 losses in a row: Reduce size to 25%
    - 7 losses in a row: PAUSE trading for 1 hour
    - 2 wins in a row: Increase size by 25%
    - 4 wins in a row: Return to 100% size
    """
    
    def __init__(self):
        self.state = DrawdownState(last_reset=datetime.now())
        self.logger = logger
        
        # Thresholds
        self.loss_threshold_1 = 3  # First warning
        self.loss_threshold_2 = 5  # Serious protection
        self.loss_threshold_3 = 7  # Emergency stop
        
        self.win_threshold_1 = 2  # Start recovery
        self.win_threshold_2 = 4  # Full recovery
        
        # Size multipliers
        self.size_reduction_1 = 0.50  # 50% size
        self.size_reduction_2 = 0.25  # 25% size
        self.size_reduction_3 = 0.00  # STOP trading
        
        # Pause duration
        self.pause_duration_minutes = 60
        self.pause_until: Optional[datetime] = None
        
        self.logger.info("✅ Drawdown Protection initialized")
    
    def record_trade_result(self, is_win: bool, pnl_pct: float, balance: float):
        """Record trade outcome and update protection state"""
        
        # Update peak balance
        if balance > self.state.peak_balance:
            self.state.peak_balance = balance
        
        # Calculate drawdown
        if self.state.peak_balance > 0:
            self.state.current_drawdown_pct = (
                (self.state.peak_balance - balance) / self.state.peak_balance * 100
            )
        
        if is_win:
            self.state.consecutive_wins += 1
            self.state.consecutive_losses = 0
            self.logger.info(f"✅ WIN: {pnl_pct:+.2f}% | Streak: {self.state.consecutive_wins} wins")
            
            # Recovery logic
            if self.state.recovery_mode:
                if self.state.consecutive_wins >= self.win_threshold_2:
                    # Full recovery
                    self.state.size_multiplier = 1.0
                    self.state.recovery_mode = False
                    self.logger.info(f"🎉 FULL RECOVERY: {self.state.consecutive_wins} wins, back to 100% size")
                
                elif self.state.consecutive_wins >= self.win_threshold_1:
                    # Partial recovery
                    self.state.size_multiplier = min(1.0, self.state.size_multiplier + 0.25)
                    self.logger.info(
                        f"📈 RECOVERY: {self.state.consecutive_wins} wins, size now {self.state.size_multiplier*100:.0f}%"
                    )
        
        else:
            self.state.consecutive_losses += 1
            self.state.consecutive_wins = 0
            self.logger.warning(f"❌ LOSS: {pnl_pct:+.2f}% | Streak: {self.state.consecutive_losses} losses")
            
            # Protection logic
            if self.state.consecutive_losses >= self.loss_threshold_3:
                # EMERGENCY STOP
                self.state.size_multiplier = self.size_reduction_3
                self.state.recovery_mode = True
                self.pause_until = datetime.now() + timedelta(minutes=self.pause_duration_minutes)
                self.logger.error(
                    f"🚨 EMERGENCY STOP: {self.state.consecutive_losses} losses! "
                    f"Pausing trading for {self.pause_duration_minutes} minutes"
                )
            
            elif self.state.consecutive_losses >= self.loss_threshold_2:
                # Severe reduction
                self.state.size_multiplier = self.size_reduction_2
                self.state.recovery_mode = True
                self.logger.error(
                    f"⚠️ SEVERE DRAWDOWN: {self.state.consecutive_losses} losses, reducing to 25% size"
                )
            
            elif self.state.consecutive_losses >= self.loss_threshold_1:
                # Moderate reduction
                self.state.size_multiplier = self.size_reduction_1
                self.state.recovery_mode = True
                self.logger.warning(
                    f"⚠️ DRAWDOWN PROTECTION: {self.state.consecutive_losses} losses, reducing to 50% size"
                )
    
    def should_allow_trading(self) -> tuple[bool, str]:
        """Check if trading is allowed or paused"""
        
        # Check if in emergency pause
        if self.pause_until and datetime.now() < self.pause_until:
            remaining = (self.pause_until - datetime.now()).seconds // 60
            return False, f"Emergency pause active ({remaining} min remaining)"
        
        # Clear pause if expired
        if self.pause_until and datetime.now() >= self.pause_until:
            self.pause_until = None
            self.state.size_multiplier = 0.25  # Resume at 25% size
            self.logger.info("⏰ Emergency pause expired, resuming at 25% size")
        
        return True, "Trading allowed"
    
    def get_size_multiplier(self) -> float:
        """Get current position size multiplier (0.0 to 1.0)"""
        return self.state.size_multiplier
    
    def is_recovery_mode(self) -> bool:
        """Check if in recovery mode"""
        return self.state.recovery_mode
    
    def get_status_summary(self) -> str:
        """Get formatted status"""
        status_lines = []
        
        if self.pause_until and datetime.now() < self.pause_until:
            remaining = (self.pause_until - datetime.now()).seconds // 60
            status_lines.append(f"🚨 PAUSED ({remaining}min)")
        elif self.state.recovery_mode:
            status_lines.append(f"🔄 RECOVERY MODE")
        else:
            status_lines.append(f"✅ NORMAL")
        
        status_lines.append(f"Size: {self.state.size_multiplier*100:.0f}%")
        status_lines.append(f"Streak: {self.state.consecutive_wins}W / {self.state.consecutive_losses}L")
        status_lines.append(f"Drawdown: {self.state.current_drawdown_pct:.1f}%")
        
        return " | ".join(status_lines)
    
    def reset(self):
        """Reset protection state (use after good performance)"""
        self.state = DrawdownState(last_reset=datetime.now())
        self.pause_until = None
        self.logger.info("🔄 Drawdown protection reset")


# Global instance
drawdown_protection = DrawdownProtection()
