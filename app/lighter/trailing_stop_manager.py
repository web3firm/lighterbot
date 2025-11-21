"""
Trailing Stop Manager - Client-side implementation using SDK's modify_order()
Since Lighter SDK has no native trailing stops, this implements the logic client-side.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional, Callable, List
from dataclasses import dataclass, field
import time

logger = logging.getLogger(__name__)


@dataclass
class TrailingStopConfig:
    """Configuration for trailing stop functionality"""
    position_id: str  # Unique position identifier
    market_index: int  # Market index for the position
    sl_order_index: int  # The stop-loss order ID to modify
    position_side: str  # 'long' or 'short'
    entry_price: Decimal
    current_sl_price: Decimal
    position_size: Decimal  # Base amount for modify_order
    
    # Trailing parameters
    trail_percent: Decimal  # e.g., 2.0 = trail 2% behind peak
    callback_distance: Decimal  # e.g., 0.5 = wait for 0.5% move before updating
    activation_profit: Optional[Decimal] = None  # e.g., 1.0 = activate after 1% profit
    
    # Runtime tracking
    peak_price: Optional[Decimal] = None  # Best price achieved
    last_update_price: Optional[Decimal] = None  # Price when last updated
    activated: bool = False  # Whether trailing has been activated
    enabled: bool = True


class TrailingStopManager:
    """
    Manages trailing stops using SDK's modify_order() method.
    
    Features:
    - Monitor price movements via WebSocket or polling
    - Automatically adjust stop-loss as price moves favorably
    - Optional activation threshold (only trail after X% profit)
    - Configurable trail distance and callback
    
    Usage:
        manager = TrailingStopManager(signer_client)
        
        # Enable trailing for a position
        await manager.enable_trailing_stop(
            position_id='position_123',
            market_index=0,
            sl_order_index=100002,
            position_side='long',
            entry_price=Decimal('3000'),
            current_sl_price=Decimal('2950'),
            position_size=100000,
            trail_percent=Decimal('2.0'),
            callback_distance=Decimal('0.5'),
            activation_profit=Decimal('1.0')
        )
        
        # Feed price updates
        await manager.update_price('position_123', Decimal('3050'))
        
        # Disable when position closes
        manager.disable_trailing_stop('position_123')
    """
    
    def __init__(self, signer_client, price_precision: int = 2):
        """
        Initialize trailing stop manager.
        
        Args:
            signer_client: Lighter SDK SignerClient instance
            price_precision: Number of decimal places for price calculations
        """
        self.signer_client = signer_client
        self.price_precision = price_precision
        
        # Tracking
        self._trailing_configs: Dict[str, TrailingStopConfig] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("✅ Trailing Stop Manager initialized")
    
    async def enable_trailing_stop(
        self,
        position_id: str,
        market_index: int,
        sl_order_index: int,
        position_side: str,
        entry_price: Decimal,
        current_sl_price: Decimal,
        position_size: Decimal,
        trail_percent: Decimal,
        callback_distance: Decimal = Decimal('0.5'),
        activation_profit: Optional[Decimal] = None
    ) -> bool:
        """
        Enable trailing stop for a position.
        
        Args:
            position_id: Unique identifier for the position
            market_index: Market index (e.g., 0 for ETH-USD)
            sl_order_index: The stop-loss order ID to modify
            position_side: 'long' or 'short'
            entry_price: Position entry price
            current_sl_price: Current stop-loss trigger price
            position_size: Position size in base units (for modify_order)
            trail_percent: Trail distance as percentage (e.g., 2.0 = 2%)
            callback_distance: Minimum price move % before updating SL
            activation_profit: Optional profit % before activating trailing
        
        Returns:
            True if enabled successfully
        """
        config = TrailingStopConfig(
            position_id=position_id,
            market_index=market_index,
            sl_order_index=sl_order_index,
            position_side=position_side.lower(),
            entry_price=entry_price,
            current_sl_price=current_sl_price,
            position_size=position_size,
            trail_percent=trail_percent,
            callback_distance=callback_distance,
            activation_profit=activation_profit,
            peak_price=entry_price,
            last_update_price=entry_price
        )
        
        # Check if should be immediately activated
        if activation_profit is None:
            config.activated = True
        
        self._trailing_configs[position_id] = config
        
        logger.info(
            f"✅ Trailing stop enabled for {position_id}: "
            f"side={position_side}, entry={entry_price}, sl={current_sl_price}, "
            f"trail={trail_percent}%, callback={callback_distance}%"
        )
        
        return True
    
    def disable_trailing_stop(self, position_id: str) -> bool:
        """
        Disable trailing stop for a position.
        
        Args:
            position_id: Position identifier
        
        Returns:
            True if disabled successfully
        """
        if position_id in self._trailing_configs:
            del self._trailing_configs[position_id]
            logger.info(f"Trailing stop disabled for {position_id}")
            return True
        return False
    
    async def update_price(self, position_id: str, current_price: Decimal) -> Optional[Decimal]:
        """
        Update price for a position and check if SL should be adjusted.
        Call this method whenever you receive a price update (WebSocket or polling).
        
        Args:
            position_id: Position identifier
            current_price: Current market price
        
        Returns:
            New stop-loss price if updated, None if no update needed
        """
        if position_id not in self._trailing_configs:
            return None
        
        config = self._trailing_configs[position_id]
        
        if not config.enabled:
            return None
        
        # Check if trailing should be activated
        if not config.activated and config.activation_profit:
            profit_pct = self._calculate_profit_pct(
                config.entry_price, 
                current_price, 
                config.position_side
            )
            
            if profit_pct >= config.activation_profit:
                config.activated = True
                logger.info(
                    f"🟢 Trailing stop activated for {position_id} "
                    f"(profit: {profit_pct:.2f}%)"
                )
        
        if not config.activated:
            return None
        
        # Update peak price
        if config.position_side == 'long':
            if current_price > config.peak_price:
                config.peak_price = current_price
        else:  # short
            if current_price < config.peak_price:
                config.peak_price = current_price
        
        # Calculate new stop-loss price
        new_sl_price = self._calculate_trailing_sl(config)
        
        # Check if update is needed
        should_update = self._should_update_sl(
            config.current_sl_price,
            new_sl_price,
            config.position_side,
            config.callback_distance,
            config.last_update_price,
            current_price
        )
        
        if should_update:
            success = await self._update_sl_order(config, new_sl_price)
            
            if success:
                config.current_sl_price = new_sl_price
                config.last_update_price = current_price
                
                logger.info(
                    f"📈 Trailing SL updated for {position_id}: "
                    f"new_sl={new_sl_price}, peak={config.peak_price}, "
                    f"current={current_price}"
                )
                
                return new_sl_price
        
        return None
    
    def _calculate_profit_pct(
        self, 
        entry_price: Decimal, 
        current_price: Decimal, 
        side: str
    ) -> Decimal:
        """Calculate profit percentage"""
        if side == 'long':
            return ((current_price - entry_price) / entry_price) * 100
        else:
            return ((entry_price - current_price) / entry_price) * 100
    
    def _calculate_trailing_sl(self, config: TrailingStopConfig) -> Decimal:
        """Calculate new trailing stop-loss price"""
        trail_multiplier = Decimal('1') - (config.trail_percent / Decimal('100'))
        
        if config.position_side == 'long':
            # For long: SL trails below peak
            new_sl = config.peak_price * trail_multiplier
        else:
            # For short: SL trails above peak (lower is better for shorts)
            trail_multiplier = Decimal('1') + (config.trail_percent / Decimal('100'))
            new_sl = config.peak_price * trail_multiplier
        
        return new_sl.quantize(Decimal(10) ** -self.price_precision)
    
    def _should_update_sl(
        self,
        current_sl: Decimal,
        new_sl: Decimal,
        side: str,
        callback_distance: Decimal,
        last_update_price: Decimal,
        current_price: Decimal
    ) -> bool:
        """
        Determine if stop-loss should be updated.
        
        Conditions:
        1. New SL must be better than current SL (closer to current price)
        2. Price must have moved enough since last update (callback_distance)
        """
        # Check if new SL is better
        if side == 'long':
            if new_sl <= current_sl:
                return False  # New SL must be higher for longs
        else:
            if new_sl >= current_sl:
                return False  # New SL must be lower for shorts
        
        # Check callback distance
        price_move_pct = abs(
            ((current_price - last_update_price) / last_update_price) * 100
        )
        
        if price_move_pct < callback_distance:
            return False
        
        return True
    
    async def _update_sl_order(
        self, 
        config: TrailingStopConfig, 
        new_sl_price: Decimal
    ) -> bool:
        """
        Update stop-loss order using SDK's modify_order().
        
        Args:
            config: Trailing stop configuration
            new_sl_price: New stop-loss trigger price
        
        Returns:
            True if update successful
        """
        try:
            # Scale price to SDK format (likely needs multiplication)
            # Note: Adjust scaling based on your market's price decimals
            scaled_price = int(new_sl_price * Decimal('100'))  # Example: $3000 -> 300000
            
            # Call SDK's modify_order
            result = self.signer_client.modify_order(
                market_index=config.market_index,
                order_index=config.sl_order_index,
                base_amount=int(config.position_size),
                price=scaled_price,
                trigger_price=scaled_price
            )
            
            logger.info(
                f"✅ Modified SL order {config.sl_order_index}: "
                f"new_trigger={new_sl_price}"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"❌ Failed to modify SL order {config.sl_order_index}: {e}"
            )
            return False
    
    def get_trailing_status(self, position_id: str) -> Optional[Dict]:
        """
        Get current trailing stop status.
        
        Args:
            position_id: Position identifier
        
        Returns:
            Dictionary with trailing status or None
        """
        if position_id not in self._trailing_configs:
            return None
        
        config = self._trailing_configs[position_id]
        
        profit_pct = self._calculate_profit_pct(
            config.entry_price,
            config.peak_price,
            config.position_side
        )
        
        return {
            'position_id': position_id,
            'side': config.position_side,
            'entry_price': float(config.entry_price),
            'current_sl': float(config.current_sl_price),
            'peak_price': float(config.peak_price),
            'trail_percent': float(config.trail_percent),
            'profit_pct': float(profit_pct),
            'activated': config.activated,
            'enabled': config.enabled
        }
    
    def get_all_trailing_positions(self) -> List[str]:
        """Get list of all positions with trailing stops enabled"""
        return list(self._trailing_configs.keys())
    
    async def start_monitoring(self, price_callback: Callable[[str], Decimal]):
        """
        Start background monitoring task (optional).
        If you prefer, just call update_price() directly from your main loop.
        
        Args:
            price_callback: Async function that returns current price for a position_id
        """
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop(price_callback))
        logger.info("Started trailing stop monitor")
    
    async def stop_monitoring(self):
        """Stop background monitoring task"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped trailing stop monitor")
    
    async def _monitor_loop(self, price_callback: Callable[[str], Decimal]):
        """Background monitoring loop (if using start_monitoring)"""
        while self._running:
            try:
                for position_id in list(self._trailing_configs.keys()):
                    try:
                        current_price = await price_callback(position_id)
                        await self.update_price(position_id, current_price)
                    except Exception as e:
                        logger.error(
                            f"Error updating trailing stop for {position_id}: {e}"
                        )
                
                await asyncio.sleep(1)  # Check every second
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in trailing stop monitor loop: {e}")
                await asyncio.sleep(5)
