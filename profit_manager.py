"""
Enterprise-grade profit management with scaled exits
"""
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from config import settings

logger = logging.getLogger(__name__)


@dataclass
class ProfitLevel:
    """Single profit taking level"""
    level_num: int
    trigger_percent: float
    size_percent: int
    trigger_price: float
    size: float
    filled: bool = False
    filled_time: Optional[datetime] = None
    filled_price: Optional[float] = None


@dataclass
class RunnerConfig:
    """Trailing stop configuration for runner position"""
    size_percent: int
    size: float
    activation_percent: float
    activation_price: float
    trailing_distance_percent: float
    activated: bool = False
    highest_price: float = 0.0
    current_trailing_stop: float = 0.0


@dataclass
class ScaledExitPlan:
    """Complete scaled exit plan for a position"""
    trade_id: str
    direction: str
    entry_price: float
    total_size: float
    stop_loss_price: float
    profit_levels: List[ProfitLevel]
    runner: RunnerConfig
    remaining_size: float
    
    def __post_init__(self):
        """Calculate remaining size"""
        self.remaining_size = self.total_size


class ProfitManager:
    """
    Enterprise-grade profit management
    
    Handles:
    - Multiple profit levels
    - Partial exits at each level
    - Trailing stop for runner position
    - Position tracking
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.active_plans: Dict[str, ScaledExitPlan] = {}
    
    def create_exit_plan(
        self,
        trade_id: str,
        direction: str,
        entry_price: float,
        total_size: float,
        stop_loss_price: float
    ) -> ScaledExitPlan:
        """
        Create scaled exit plan for a trade
        
        Args:
            trade_id: Unique trade identifier
            direction: "long" or "short"
            entry_price: Entry price
            total_size: Total position size
            stop_loss_price: Initial stop loss price
            
        Returns:
            ScaledExitPlan with all profit levels configured
        """
        profit_levels = []
        
        # Level 1: First profit target
        level1_size = total_size * (settings.profit_level_1_size / 100.0)
        if direction == "long":
            level1_trigger = entry_price * (1 + settings.profit_level_1_percent / 100)
        else:
            level1_trigger = entry_price * (1 - settings.profit_level_1_percent / 100)
        
        profit_levels.append(ProfitLevel(
            level_num=1,
            trigger_percent=settings.profit_level_1_percent,
            size_percent=settings.profit_level_1_size,
            trigger_price=level1_trigger,
            size=level1_size
        ))
        
        # Level 2: Second profit target
        level2_size = total_size * (settings.profit_level_2_size / 100.0)
        if direction == "long":
            level2_trigger = entry_price * (1 + settings.profit_level_2_percent / 100)
        else:
            level2_trigger = entry_price * (1 - settings.profit_level_2_percent / 100)
        
        profit_levels.append(ProfitLevel(
            level_num=2,
            trigger_percent=settings.profit_level_2_percent,
            size_percent=settings.profit_level_2_size,
            trigger_price=level2_trigger,
            size=level2_size
        ))
        
        # Runner: Trailing stop portion
        runner_size = total_size * (settings.profit_runner_size / 100.0)
        if direction == "long":
            activation_price = entry_price * (1 + settings.trailing_stop_activation / 100)
        else:
            activation_price = entry_price * (1 - settings.trailing_stop_activation / 100)
        
        runner = RunnerConfig(
            size_percent=settings.profit_runner_size,
            size=runner_size,
            activation_percent=settings.trailing_stop_activation,
            activation_price=activation_price,
            trailing_distance_percent=settings.trailing_stop_distance,
            highest_price=entry_price
        )
        
        plan = ScaledExitPlan(
            trade_id=trade_id,
            direction=direction,
            entry_price=entry_price,
            total_size=total_size,
            stop_loss_price=stop_loss_price,
            profit_levels=profit_levels,
            runner=runner
        )
        
        self.active_plans[trade_id] = plan
        
        self.logger.info(f"📊 Created scaled exit plan for {trade_id}")
        self.logger.info(f"   Entry: ${entry_price:.2f}")
        self.logger.info(f"   Total Size: {total_size:.6f}")
        self.logger.info(f"   Level 1: {settings.profit_level_1_size}% at ${level1_trigger:.2f} (+{settings.profit_level_1_percent}%)")
        self.logger.info(f"   Level 2: {settings.profit_level_2_size}% at ${level2_trigger:.2f} (+{settings.profit_level_2_percent}%)")
        self.logger.info(f"   Runner: {settings.profit_runner_size}% trails after ${activation_price:.2f} (+{settings.trailing_stop_activation}%)")
        self.logger.info(f"   Stop Loss: ${stop_loss_price:.2f} (-{settings.stop_loss_percent}%)")
        
        return plan
    
    def update_trailing_stop(
        self,
        trade_id: str,
        current_price: float
    ) -> Optional[float]:
        """
        Update trailing stop for runner position
        
        Args:
            trade_id: Trade identifier
            current_price: Current market price
            
        Returns:
            New trailing stop price if updated, None otherwise
        """
        if trade_id not in self.active_plans:
            return None
        
        plan = self.active_plans[trade_id]
        runner = plan.runner
        
        # Check if we should activate trailing
        if not runner.activated:
            if plan.direction == "long":
                if current_price >= runner.activation_price:
                    runner.activated = True
                    runner.highest_price = current_price
                    self.logger.info(f"🎯 Trailing stop ACTIVATED for {trade_id} at ${current_price:.2f}")
            else:  # short
                if current_price <= runner.activation_price:
                    runner.activated = True
                    runner.highest_price = current_price
                    self.logger.info(f"🎯 Trailing stop ACTIVATED for {trade_id} at ${current_price:.2f}")
        
        # Update trailing stop if activated
        if runner.activated:
            # Update highest price
            if plan.direction == "long":
                if current_price > runner.highest_price:
                    runner.highest_price = current_price
                    # Calculate new trailing stop
                    new_stop = current_price * (1 - runner.trailing_distance_percent / 100)
                    
                    # Only move stop up, never down
                    if new_stop > runner.current_trailing_stop:
                        old_stop = runner.current_trailing_stop
                        runner.current_trailing_stop = new_stop
                        self.logger.info(f"📈 Trailing stop moved: ${old_stop:.2f} → ${new_stop:.2f} (peak: ${runner.highest_price:.2f})")
                        return new_stop
            else:  # short
                if current_price < runner.highest_price:
                    runner.highest_price = current_price
                    # Calculate new trailing stop
                    new_stop = current_price * (1 + runner.trailing_distance_percent / 100)
                    
                    # Only move stop down, never up
                    if new_stop < runner.current_trailing_stop or runner.current_trailing_stop == 0:
                        old_stop = runner.current_trailing_stop
                        runner.current_trailing_stop = new_stop
                        self.logger.info(f"📉 Trailing stop moved: ${old_stop:.2f} → ${new_stop:.2f} (low: ${runner.highest_price:.2f})")
                        return new_stop
        
        return None
    
    def check_profit_levels(
        self,
        trade_id: str,
        current_price: float
    ) -> List[ProfitLevel]:
        """
        Check which profit levels have been hit
        
        Args:
            trade_id: Trade identifier
            current_price: Current market price
            
        Returns:
            List of ProfitLevel objects that should be executed
        """
        if trade_id not in self.active_plans:
            return []
        
        plan = self.active_plans[trade_id]
        triggered_levels = []
        
        for level in plan.profit_levels:
            if level.filled:
                continue
            
            # Check if level triggered
            if plan.direction == "long":
                if current_price >= level.trigger_price:
                    triggered_levels.append(level)
            else:  # short
                if current_price <= level.trigger_price:
                    triggered_levels.append(level)
        
        return triggered_levels
    
    def mark_level_filled(
        self,
        trade_id: str,
        level_num: int,
        filled_price: float
    ):
        """Mark a profit level as filled"""
        if trade_id not in self.active_plans:
            return
        
        plan = self.active_plans[trade_id]
        for level in plan.profit_levels:
            if level.level_num == level_num:
                level.filled = True
                level.filled_time = datetime.now()
                level.filled_price = filled_price
                
                # Update remaining size
                plan.remaining_size -= level.size
                
                profit = level.size * abs(filled_price - plan.entry_price)
                self.logger.info(f"✅ Level {level_num} filled: {level.size:.6f} @ ${filled_price:.2f} (+${profit:.2f})")
                self.logger.info(f"   Remaining position: {plan.remaining_size:.6f}")
                break
    
    def get_plan(self, trade_id: str) -> Optional[ScaledExitPlan]:
        """Get exit plan for a trade"""
        return self.active_plans.get(trade_id)
    
    def remove_plan(self, trade_id: str):
        """Remove exit plan (trade closed)"""
        if trade_id in self.active_plans:
            del self.active_plans[trade_id]
            self.logger.info(f"Removed exit plan for {trade_id}")
    
    def get_statistics(self, trade_id: str) -> Dict:
        """Get statistics for a scaled exit plan"""
        if trade_id not in self.active_plans:
            return {}
        
        plan = self.active_plans[trade_id]
        
        total_profit = 0.0
        levels_filled = 0
        
        for level in plan.profit_levels:
            if level.filled:
                levels_filled += 1
                profit = level.size * abs(level.filled_price - plan.entry_price)
                total_profit += profit
        
        return {
            "trade_id": trade_id,
            "entry_price": plan.entry_price,
            "total_size": plan.total_size,
            "remaining_size": plan.remaining_size,
            "levels_filled": levels_filled,
            "total_levels": len(plan.profit_levels),
            "total_profit_locked": total_profit,
            "runner_activated": plan.runner.activated,
            "runner_size": plan.runner.size,
            "highest_price": plan.runner.highest_price if plan.runner.activated else None,
            "trailing_stop": plan.runner.current_trailing_stop if plan.runner.activated else None
        }


# Global instance
profit_manager = ProfitManager()
