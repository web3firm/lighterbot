"""
Hybrid Exit Manager - OCO (Exchange) + Bot (Advanced Features)

This manager handles the best of both worlds:
1. Exchange OCO manages basic TP/SL (instant, 0ms delay, survives crashes)
2. Bot manages advanced features (trailing stops, early exits, momentum shifts)
"""
import asyncio
from typing import Dict, Optional
from datetime import datetime
from logger import logger
from config import settings


class HybridExitManager:
    """
    Manages hybrid exit strategy:
    - Exchange handles basic TP (+2%) and SL (-2%)
    - Bot handles trailing stops (peak +3% → exit +1%)
    - Bot handles early exits (momentum shift, setup failure)
    """
    
    def __init__(self, order_manager):
        self.order_manager = order_manager
        self.logger = logger
        
        # Track position states
        self.trailing_active: Dict[str, bool] = {}
        self.recently_closed: set = set()
        
    async def check_position_for_hybrid_exit(
        self,
        position,
        pnl_pct: float,
        highest_pnl: float,
        position_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if position should be exited by bot (hybrid mode)
        
        Returns:
            (should_close, reason)
        """
        # Check if already closed
        if position_id in self.recently_closed:
            return False, None
        
        # Check if OCO is active
        has_oco = position_id in self.order_manager.oco_orders
        trailing_active = self.trailing_active.get(position_id, False)
        
        if has_oco and not trailing_active:
            # ========================================
            # OCO MODE: Exchange managing TP/SL
            # ========================================
            # FIXED LOGIC: Bot trails at +1.5%, Exchange TP at +3% (backup)
            
            # 1. TRAILING ACTIVATION: Peak +1.5% → Cancel TP, bot takes over
            # This activates BEFORE exchange TP (+3%), allowing trailing to work!
            if highest_pnl >= 1.5:
                self.logger.info(f"🔄 TRAILING ACTIVATION: Peaked +{highest_pnl:.2f}%")
                self.logger.info(f"   Cancelling exchange TP (+3%), bot trailing at +0.5%")
                
                # Cancel exchange TP so it doesn't interfere
                cancelled = await self.order_manager.cancel_oco_tp(position_id)
                
                if cancelled:
                    self.trailing_active[position_id] = True
                    self.logger.info(f"✅ Bot trailing active - will exit if drops to +0.5%")
                else:
                    self.logger.error(f"❌ Failed to cancel TP - exchange may close at +3%")
            
            # 2. EARLY EXIT: Momentum shift detection
            # Example: If strong reversal signal, close early
            # early_exit = await self.check_early_exit_signal(position)
            # if early_exit:
            #     await self.order_manager.cancel_oco_tp(position_id)
            #     return True, "Early exit: momentum shift"
            
            # Exchange OCO handles exits (TP @ +3%, SL @ -2%)
            return False, None
            
        elif trailing_active:
            # ========================================
            # BOT TRAILING MODE
            # ========================================
            # Exchange TP cancelled, bot managing exit
            
            # Exit at +0.5% after peaking at +1.5%
            # This locks in profit while giving room to run
            if highest_pnl >= 1.5 and pnl_pct <= 0.5:
                self.logger.warning(f"🔄 TRAILING STOP: Peaked +{highest_pnl:.2f}%, now {pnl_pct:.2f}%")
                return True, f"Trailing stop: peaked +{highest_pnl:.2f}%"
            
            return False, None
            
        else:
            # ========================================
            # FALLBACK MODE: No OCO, bot manages everything
            # ========================================
            # This happens if OCO creation failed
            
            # Take-profit: +2%
            if pnl_pct >= 2.0:
                self.logger.warning(f"💰 TAKE-PROFIT: {pnl_pct:.2f}%")
                return True, "Take-profit +2%"
            
            # Stop-loss: -2%
            if pnl_pct <= -settings.stop_loss_percent:
                self.logger.warning(f"🛑 STOP-LOSS: {pnl_pct:.2f}%")
                return True, f"Stop-loss -{settings.stop_loss_percent}%"
            
            return False, None
    
    async def close_position_hybrid(
        self,
        position,
        reason: str,
        position_id: str
    ) -> bool:
        """
        Close position in hybrid mode
        
        Returns:
            True if closed successfully
        """
        try:
            # Mark as closed BEFORE API call (prevents race condition)
            self.recently_closed.add(position_id)
            
            # Determine side
            side = "sell" if position.is_long else "buy"
            
            # Place close order
            success = await self.order_manager.place_market_order(
                side=side,
                size=abs(position.size),
                market_id=position.market_id
            )
            
            if success:
                self.logger.info(f"✅ Position closed: {reason}")
                
                # Cancel any remaining OCO orders
                await self.order_manager.cancel_oco_sl(position_id)
                await self.order_manager.cleanup_oco(position_id)
                
                # Cleanup tracking
                if position_id in self.trailing_active:
                    del self.trailing_active[position_id]
                
                return True
            else:
                # Restore if failed
                self.recently_closed.discard(position_id)
                return False
                
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            self.recently_closed.discard(position_id)
            return False
    
    async def check_early_exit_signal(self, position) -> bool:
        """
        Check if position should be exited early due to:
        - Momentum shift
        - Setup invalidation
        - Volume decline
        - etc.
        
        Override this with your custom early exit logic
        """
        # TODO: Implement sophisticated early exit detection
        # Examples:
        # - Check if momentum indicators reversed
        # - Check if volume dropped significantly
        # - Check if support/resistance broke
        # - Check if orderflow reversed
        
        return False
    
    def cleanup_closed_position(self, position_id: str):
        """Clean up tracking for closed position"""
        self.recently_closed.discard(position_id)
        if position_id in self.trailing_active:
            del self.trailing_active[position_id]


# Singleton instance
hybrid_exit_manager = None


def get_hybrid_exit_manager(order_manager):
    """Get or create hybrid exit manager"""
    global hybrid_exit_manager
    if hybrid_exit_manager is None:
        hybrid_exit_manager = HybridExitManager(order_manager)
    return hybrid_exit_manager
