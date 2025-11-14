"""
Simple profit management with 3 static exit levels
No ML, no trailing stops - just clean exits
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
    size: float
    filled: bool = False
    filled_time: Optional[datetime] = None
    filled_price: Optional[float] = None


@dataclass
class ScaledExitPlan:
    """Complete scaled exit plan for a position"""
    trade_id: str
    direction: str
    entry_price: float
    total_size: float
    stop_loss_price: float
    profit_levels: List[ProfitLevel]
    remaining_size: float = 0.0
    
    def __post_init__(self):
        """Calculate remaining size"""
        self.remaining_size = self.total_size


class ProfitManager:
    """
    Simple profit management with 3 static levels:
    - Level 1: +2% → Exit 40%
    - Level 2: +3% → Exit 30%
    - Level 3: +4% → Exit 30%
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
        
        # Level 1: Quick profit at +2% (40% exit)
        level1_size = total_size * (settings.profit_level_1_size / 100.0)
        profit_levels.append(ProfitLevel(
            level_num=1,
            trigger_percent=settings.profit_level_1_percent,
            size_percent=settings.profit_level_1_size,
            size=level1_size
        ))
        
        # Level 2: Second exit at +3% (30% exit)
        level2_size = total_size * (settings.profit_level_2_size / 100.0)
        profit_levels.append(ProfitLevel(
            level_num=2,
            trigger_percent=settings.profit_level_2_percent,
            size_percent=settings.profit_level_2_size,
            size=level2_size
        ))
        
        # Level 3: Final exit at +4% (30% exit)
        level3_size = total_size * (settings.profit_level_3_size / 100.0)
        profit_levels.append(ProfitLevel(
            level_num=3,
            trigger_percent=settings.profit_level_3_percent,
            size_percent=settings.profit_level_3_size,
            size=level3_size
        ))
        
        plan = ScaledExitPlan(
            trade_id=trade_id,
            direction=direction,
            entry_price=entry_price,
            total_size=total_size,
            stop_loss_price=stop_loss_price,
            profit_levels=profit_levels,
            remaining_size=total_size
        )
        
        self.active_plans[trade_id] = plan
        
        self.logger.info(f"📊 Created exit plan for {trade_id}")
        self.logger.info(f"   Entry: ${entry_price:.2f}, Size: {total_size:.4f}")
        self.logger.info(f"   L1: {settings.profit_level_1_size}% @ +{settings.profit_level_1_percent}%")
        self.logger.info(f"   L2: {settings.profit_level_2_size}% @ +{settings.profit_level_2_percent}%")
        self.logger.info(f"   L3: {settings.profit_level_3_size}% @ +{settings.profit_level_3_percent}%")
        self.logger.info(f"   Stop Loss: -{ settings.stop_loss_percent}%")
        
        return plan
    
    def check_profit_levels(
        self,
        trade_id: str,
        current_pnl_percent: float
    ) -> List[ProfitLevel]:
        """
        Check which profit levels have been hit
        
        Args:
            trade_id: Trade identifier
            current_pnl_percent: Current P&L percentage
            
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
                if current_pnl_percent >= level.trigger_percent:
                    self.logger.info(f"✅ Level {level.level_num} triggered: PnL {current_pnl_percent:.2f}% >= {level.trigger_percent:.2f}%")
                    triggered_levels.append(level)
            else:  # short
                if current_pnl_percent >= level.trigger_percent:  # For shorts, PnL is already calculated correctly
                    self.logger.info(f"✅ Level {level.level_num} triggered: PnL {current_pnl_percent:.2f}% >= {level.trigger_percent:.2f}%")
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
                self.logger.info(f"✅ Level {level_num} filled: {level.size:.4f} @ ${filled_price:.2f} (Profit: +${profit:.2f})")
                self.logger.info(f"   Remaining position: {plan.remaining_size:.4f}")
                break
    
    def has_plan(self, trade_id: str) -> bool:
        """Check if a plan exists for this trade"""
        return trade_id in self.active_plans
    
    def get_plan(self, trade_id: str) -> Optional[ScaledExitPlan]:
        """Get exit plan for a trade"""
        return self.active_plans.get(trade_id)
    
    def remove_plan(self, trade_id: str):
        """Remove exit plan (trade fully closed)"""
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
            "total_profit_locked": total_profit
        }


# Global instance
profit_manager = ProfitManager()
