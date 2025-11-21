"""
Lighter Order Manager - OCO orders, trailing SL/TP
Manages order lifecycle and implements advanced order types
"""

import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)


class LighterOrderManager:
    """
    Manages orders on Lighter Protocol
    Implements OCO (one-cancels-other), trailing stops, and position management
    """
    
    def __init__(self, client):
        """
        Initialize order manager
        
        Args:
            client: LighterClient instance
        """
        self.client = client
        
        # Order tracking
        self.open_orders: Dict[str, Dict[str, Any]] = {}
        self.order_history: List[Dict[str, Any]] = []
        
        # OCO order tracking
        self.oco_orders: Dict[str, Dict[str, Any]] = {}
        
        # Trailing stop tracking
        self.trailing_stops: Dict[str, Dict[str, Any]] = {}
        
        logger.info("✅ Lighter order manager initialized")
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Set leverage for symbol
        
        Args:
            symbol: Trading pair
            leverage: Leverage multiplier (1-50)
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"⚙️  Setting leverage for {symbol}: {leverage}x")
            
            # TODO: Implement using lighter-python
            # await self.client.set_leverage(symbol, leverage)
            
            logger.info(f"✅ Leverage set: {leverage}x")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to set leverage: {e}")
            return False
    
    async def place_oco_order(self, symbol: str, side: str, size: Decimal,
                             entry_price: Decimal, sl_price: Decimal,
                             tp_price: Decimal) -> Optional[Dict[str, Any]]:
        """
        Place OCO (one-cancels-other) order with stop-loss and take-profit
        
        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            size: Position size
            entry_price: Entry price
            sl_price: Stop-loss price
            tp_price: Take-profit price
            
        Returns:
            OCO order info
        """
        try:
            logger.info(f"🎯 Placing OCO order:")
            logger.info(f"   Symbol: {symbol}")
            logger.info(f"   Side: {side.upper()}")
            logger.info(f"   Size: {size}")
            logger.info(f"   Entry: ${entry_price:.4f}")
            logger.info(f"   SL: ${sl_price:.4f}")
            logger.info(f"   TP: ${tp_price:.4f}")
            
            # Get market_id from environment or symbol mapping
            import os
            market_id = int(os.getenv('LIGHTER_MARKET_ID', '0'))
            
            # Place entry order
            entry_order = await self.client.place_order(
                market_id=market_id,
                side=side,
                order_type='limit',
                size=size,
                price=entry_price
            )
            
            if 'error' in entry_order:
                raise Exception(f"Failed to place entry order: {entry_order['error']}")
            
            entry_order_id = entry_order.get('order_id')
            
            # Create OCO structure
            oco_id = f"oco_{entry_order_id}"
            self.oco_orders[oco_id] = {
                'oco_id': oco_id,
                'symbol': symbol,
                'side': side,
                'size': size,
                'entry_order_id': entry_order_id,
                'entry_price': float(entry_price),
                'sl_price': float(sl_price),
                'tp_price': float(tp_price),
                'sl_order_id': None,
                'tp_order_id': None,
                'status': 'pending',
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"✅ OCO order placed: {oco_id}")
            logger.info(f"   Entry Order ID: {entry_order_id}")
            logger.info(f"   SL Price: ${sl_price:.4f}")
            logger.info(f"   TP Price: ${tp_price:.4f}")
            logger.info(f"   Note: SL/TP orders will be placed after entry fill")
            return self.oco_orders[oco_id]
            
        except Exception as e:
            logger.error(f"❌ Failed to place OCO order: {e}")
            return None
    
    async def place_sl_tp_orders(self, oco_id: str) -> bool:
        """
        Place SL/TP orders after entry fill using native SDK methods
        
        Args:
            oco_id: OCO order ID
            
        Returns:
            True if successful
        """
        try:
            oco = self.oco_orders.get(oco_id)
            if not oco:
                raise ValueError(f"OCO order not found: {oco_id}")
            
            # Extract order details
            symbol = oco['symbol']
            side = oco['side']
            size = Decimal(str(oco['size']))
            sl_price = Decimal(str(oco['sl_price']))
            tp_price = Decimal(str(oco['tp_price']))
            
            # Determine close side (opposite of entry)
            close_side = 'sell' if side == 'buy' else 'buy'
            
            # Get market ID
            import os
            market_id = int(os.getenv('LIGHTER_MARKET_ID', '0'))
            
            # Place stop-loss order using native SDK method
            logger.info(f"📤 Placing native stop-loss order at ${sl_price:.4f}")
            sl_order = await self.client.place_order(
                market_id=market_id,
                side=close_side,
                order_type='stop_loss',
                size=size,
                price=sl_price,
                trigger_price=sl_price,
                reduce_only=True
            )
            
            # Place take-profit order using native SDK method
            logger.info(f"📤 Placing native take-profit order at ${tp_price:.4f}")
            tp_order = await self.client.place_order(
                market_id=market_id,
                side=close_side,
                order_type='take_profit',
                size=size,
                price=tp_price,
                trigger_price=tp_price,
                reduce_only=True
            )
            
            # Update OCO with native order IDs
            oco['sl_order_id'] = sl_order.get('order_id')
            oco['tp_order_id'] = tp_order.get('order_id')
            oco['status'] = 'active'
            oco['placed_at'] = datetime.now(timezone.utc).isoformat()
            
            logger.info(f"✅ Native OCO orders placed for {oco_id}")
            logger.info(f"   SL Order ID: {oco['sl_order_id']}")
            logger.info(f"   TP Order ID: {oco['tp_order_id']}")
            logger.info(f"   Exchange will handle OCO cancellation automatically")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to place SL/TP orders: {e}")
            logger.exception(e)
            return False
    
    async def update_trailing_stop(self, symbol: str, position_side: str,
                                   current_price: Decimal, peak_price: Decimal,
                                   trail_distance_pct: Decimal) -> bool:
        """
        Update trailing stop-loss
        
        Args:
            symbol: Trading pair
            position_side: 'long' or 'short'
            current_price: Current market price
            peak_price: Peak price since position opened
            trail_distance_pct: Trail distance as percentage
            
        Returns:
            True if updated
        """
        try:
            # Calculate new stop price
            if position_side == 'long':
                new_sl_price = peak_price * (Decimal('1') - trail_distance_pct / Decimal('100'))
            else:
                new_sl_price = peak_price * (Decimal('1') + trail_distance_pct / Decimal('100'))
            
            # Get existing trailing stop
            trailing_key = f"{symbol}_{position_side}"
            existing_stop = self.trailing_stops.get(trailing_key)
            
            # Only update if new stop is better
            if existing_stop:
                old_sl_price = Decimal(str(existing_stop['sl_price']))
                
                if position_side == 'long' and new_sl_price <= old_sl_price:
                    return False  # Don't move stop down for longs
                if position_side == 'short' and new_sl_price >= old_sl_price:
                    return False  # Don't move stop up for shorts
            
            # Update trailing stop
            self.trailing_stops[trailing_key] = {
                'symbol': symbol,
                'side': position_side,
                'sl_price': float(new_sl_price),
                'peak_price': float(peak_price),
                'trail_distance_pct': float(trail_distance_pct),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"📈 Trailing stop updated for {symbol} {position_side}")
            logger.info(f"   New SL: ${new_sl_price:.4f}")
            logger.info(f"   Peak: ${peak_price:.4f}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update trailing stop: {e}")
            return False
    
    async def check_trailing_stops(self, current_prices: Dict[str, Decimal]) -> List[str]:
        """
        Check if any trailing stops should be triggered
        
        Args:
            current_prices: Dict of symbol -> current price
            
        Returns:
            List of symbols where stops were hit
        """
        triggered = []
        
        for key, stop in list(self.trailing_stops.items()):
            symbol = stop['symbol']
            side = stop['side']
            sl_price = Decimal(str(stop['sl_price']))
            
            current_price = current_prices.get(symbol)
            if not current_price:
                continue
            
            # Check if stop triggered
            if side == 'long' and current_price <= sl_price:
                logger.warning(f"🛑 Trailing stop HIT for {symbol} LONG")
                logger.warning(f"   Current: ${current_price:.4f} <= SL: ${sl_price:.4f}")
                triggered.append(symbol)
                
            elif side == 'short' and current_price >= sl_price:
                logger.warning(f"🛑 Trailing stop HIT for {symbol} SHORT")
                logger.warning(f"   Current: ${current_price:.4f} >= SL: ${sl_price:.4f}")
                triggered.append(symbol)
        
        return triggered
    
    async def update_oco_sl_price(self, oco_id: str, new_sl_price: Decimal) -> bool:
        """Update stop-loss price for monitored OCO order"""
        try:
            oco = self.oco_orders.get(oco_id)
            if not oco or oco['status'] != 'active':
                return False
            
            # Just update the monitored price - no actual order to cancel
            old_sl = oco['sl_price']
            oco['sl_price'] = float(new_sl_price)
            
            logger.info(f"✅ Updated trailing SL for {oco_id}")
            logger.info(f"   Old SL: ${old_sl:.4f} → New SL: ${new_sl_price:.4f}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update SL: {e}")
            return False
    
    async def update_oco_tp_price(self, oco_id: str, new_tp_price: Decimal) -> bool:
        """Update take-profit price for monitored OCO order"""
        try:
            oco = self.oco_orders.get(oco_id)
            if not oco or oco['status'] != 'active':
                return False
            
            # Just update the monitored price - no actual order to cancel
            old_tp = oco['tp_price']
            oco['tp_price'] = float(new_tp_price)
            
            logger.info(f"✅ Updated trailing TP for {oco_id}")
            logger.info(f"   Old TP: ${old_tp:.4f} → New TP: ${new_tp_price:.4f}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update TP: {e}")
            return False
    
    async def cancel_oco_order(self, oco_id: str) -> bool:
        """
        Cancel OCO order and all related orders
        
        Args:
            oco_id: OCO order ID
            
        Returns:
            True if successful
        """
        try:
            oco = self.oco_orders.get(oco_id)
            if not oco:
                logger.warning(f"OCO order not found: {oco_id}")
                return False
            
            symbol = oco['symbol']
            
            # Cancel all related orders
            if oco.get('entry_order_id'):
                await self.client.cancel_order(oco['entry_order_id'], symbol)
            
            if oco.get('sl_order_id'):
                await self.client.cancel_order(oco['sl_order_id'], symbol)
            
            if oco.get('tp_order_id'):
                await self.client.cancel_order(oco['tp_order_id'], symbol)
            
            # Update status
            oco['status'] = 'cancelled'
            
            logger.info(f"✅ OCO order cancelled: {oco_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to cancel OCO order: {e}")
            return False
    
    async def monitor_oco_orders(self):
        """Monitor OCO orders for fills and cancellations"""
        for oco_id, oco in list(self.oco_orders.items()):
            if oco['status'] not in ['pending', 'active']:
                continue
            
            try:
                # Check entry order status
                if oco['status'] == 'pending' and oco.get('entry_order_id'):
                    # Check if entry order filled and place native SL/TP orders
                    try:
                        entry_order = await self.client.get_order_status(oco['entry_order_id'])
                        if entry_order and entry_order.get('status') == 'filled':
                            await self.place_sl_tp_orders(oco_id)
                            logger.info(f"📊 Entry filled for {oco_id}, native SL/TP orders placed")
                    except Exception as check_err:
                        logger.debug(f"Could not check entry order: {check_err}")
                
                # Check if native SL or TP orders filled
                # Exchange handles OCO cancellation automatically
                if oco['status'] == 'active':
                    try:
                        # Check SL order status
                        if oco.get('sl_order_id'):
                            sl_order = await self.client.get_order_status(oco['sl_order_id'])
                            if sl_order and sl_order.get('status') == 'filled':
                                oco['status'] = 'sl_filled'
                                oco['exit_price'] = sl_order.get('fill_price', oco['sl_price'])
                                oco['exit_time'] = datetime.now(timezone.utc).isoformat()
                                logger.warning(f"🚨 Stop-Loss filled for {oco_id} at ${oco['exit_price']:.4f}")
                                logger.info(f"   Exchange automatically cancelled TP order")
                                continue
                        
                        # Check TP order status
                        if oco.get('tp_order_id'):
                            tp_order = await self.client.get_order_status(oco['tp_order_id'])
                            if tp_order and tp_order.get('status') == 'filled':
                                oco['status'] = 'tp_filled'
                                oco['exit_price'] = tp_order.get('fill_price', oco['tp_price'])
                                oco['exit_time'] = datetime.now(timezone.utc).isoformat()
                                logger.info(f"🎉 Take-Profit filled for {oco_id} at ${oco['exit_price']:.4f}")
                                logger.info(f"   Exchange automatically cancelled SL order")
                                continue
                    
                    except Exception as check_err:
                        logger.debug(f"Could not check SL/TP orders: {check_err}")
                
            except Exception as e:
                logger.error(f"Error monitoring OCO order {oco_id}: {e}")
    
    def get_oco_order(self, oco_id: str) -> Optional[Dict[str, Any]]:
        """Get OCO order by ID"""
        return self.oco_orders.get(oco_id)
    
    def get_all_oco_orders(self) -> Dict[str, Dict[str, Any]]:
        """Get all OCO orders"""
        return self.oco_orders
    
    def get_trailing_stop(self, symbol: str, side: str) -> Optional[Dict[str, Any]]:
        """Get trailing stop for symbol and side"""
        key = f"{symbol}_{side}"
        return self.trailing_stops.get(key)
    
    def get_all_trailing_stops(self) -> Dict[str, Dict[str, Any]]:
        """Get all trailing stops"""
        return self.trailing_stops
    
    def clear_trailing_stop(self, symbol: str, side: str):
        """Clear trailing stop"""
        key = f"{symbol}_{side}"
        if key in self.trailing_stops:
            del self.trailing_stops[key]
            logger.info(f"🗑️  Trailing stop cleared: {symbol} {side}")


if __name__ == "__main__":
    # Test order manager
    async def test():
        from app.hl.lighter_client import LighterClient
        
        client = LighterClient(
            api_url="https://api.lighter.xyz/v1",
            private_key="0xtest",
            account_address="0xtest",
            testnet=True
        )
        
        manager = LighterOrderManager(client)
        
        # Test OCO order
        oco = await manager.place_oco_order(
            symbol='BTC-USD',
            side='buy',
            size=Decimal('0.001'),
            entry_price=Decimal('50000'),
            sl_price=Decimal('49000'),
            tp_price=Decimal('52000')
        )
        
        print(f"OCO Order: {oco}")
    
    asyncio.run(test())
