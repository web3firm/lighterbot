"""
Lighter Order Manager - Native SDK Implementation
Uses Lighter SDK's native grouped orders for TRUE exchange-level OCO
Replaces 500+ lines of manual tracking with ~200 lines of SDK calls
"""

import logging
import lighter
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime, timezone
import asyncio
import os

logger = logging.getLogger(__name__)


class LighterOrderManager:
    """
    Native SDK-based order manager
    Uses create_grouped_orders() for TRUE OCO implementation
    """
    
    def __init__(self, client):
        """
        Initialize order manager with SDK client
        
        Args:
            client: LighterClient instance with signer_client
        """
        self.client = client
        self.market_id = int(os.getenv('LIGHTER_MARKET_ID', '0'))
        
        # Tracking (minimal - SDK handles most logic)
        self.active_groups: Dict[str, Dict[str, Any]] = {}
        self.order_counter = 0
        
        # API clients for data retrieval
        self.order_api = lighter.OrderApi(client.api_client)
        self.account_api = lighter.AccountApi(client.api_client)
        
        logger.info("✅ Lighter order manager initialized (Native SDK)")
    
    def _generate_order_id(self) -> int:
        """Generate unique client order ID"""
        self.order_counter += 1
        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        return (timestamp % 1000000) * 10000 + self.order_counter
    
    async def place_oco_order_native(self, symbol: str, side: str, size: Decimal,
                                     entry_price: Decimal, sl_price: Decimal,
                                     tp_price: Decimal) -> Optional[str]:
        """
        Place TRUE OCO order using SDK's native grouped orders
        Uses GROUPING_TYPE_ONE_TRIGGERS_A_ONE_CANCELS_THE_OTHER (Type 3)
        
        This creates an ATOMIC exchange-level order group where:
        1. Entry order is placed
        2. When entry fills, SL and TP orders are automatically placed
        3. When SL or TP fills, the other is automatically cancelled
        
        Args:
            symbol: Trading pair (e.g., 'ETH-USD')
            side: 'buy' or 'sell'
            size: Position size in base asset
            entry_price: Entry limit price
            sl_price: Stop-loss trigger price
            tp_price: Take-profit trigger price
            
        Returns:
            Transaction hash of the grouped order
        """
        try:
            logger.info(f"🎯 Placing NATIVE OCO order (SDK grouped order):")
            logger.info(f"   Symbol: {symbol}")
            logger.info(f"   Side: {side.upper()}")
            logger.info(f"   Size: {size}")
            logger.info(f"   Entry: ${entry_price:.4f}")
            logger.info(f"   SL: ${sl_price:.4f} (trigger)")
            logger.info(f"   TP: ${tp_price:.4f} (trigger)")
            
            # Convert to SDK units
            # Base amount: 1e4 decimals (0.01 ETH = 100000)
            # Price: 1e2 decimals ($3000.00 = 300000)
            base_amount = int(float(size) * 1e4)
            entry_price_scaled = int(float(entry_price) * 1e2)
            sl_price_scaled = int(float(sl_price) * 1e2)
            tp_price_scaled = int(float(tp_price) * 1e2)
            
            is_ask = (side.lower() == 'sell')
            
            # Create order requests using ctypes Structure
            orders = []
            
            # 1. Entry order (limit order)
            entry_req = lighter.signer_client.CreateOrderTxReq()
            entry_req.MarketIndex = self.market_id
            entry_req.ClientOrderIndex = 0  # SDK will auto-generate for grouped orders
            entry_req.BaseAmount = base_amount
            entry_req.Price = entry_price_scaled
            entry_req.IsAsk = 1 if is_ask else 0
            entry_req.Type = lighter.SignerClient.ORDER_TYPE_LIMIT
            entry_req.TimeInForce = lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME
            entry_req.ReduceOnly = 0
            entry_req.TriggerPrice = 0
            entry_req.OrderExpiry = lighter.SignerClient.DEFAULT_28_DAY_ORDER_EXPIRY
            orders.append(entry_req)
            
            # 2. Stop-loss order (triggered when entry fills)
            sl_req = lighter.signer_client.CreateOrderTxReq()
            sl_req.MarketIndex = self.market_id
            sl_req.ClientOrderIndex = 0  # SDK will auto-generate for grouped orders
            sl_req.BaseAmount = 0  # SDK inherits from entry order in group
            sl_req.Price = sl_price_scaled
            sl_req.IsAsk = 0 if is_ask else 1  # Opposite side to close
            sl_req.Type = lighter.SignerClient.ORDER_TYPE_STOP_LOSS
            sl_req.TimeInForce = lighter.SignerClient.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL  # Stop orders use IOC
            sl_req.ReduceOnly = 1  # Reduce-only to close position
            sl_req.TriggerPrice = sl_price_scaled
            sl_req.OrderExpiry = lighter.SignerClient.DEFAULT_28_DAY_ORDER_EXPIRY
            orders.append(sl_req)
            
            # 3. Take-profit order (triggered when entry fills, OCO with SL)
            tp_req = lighter.signer_client.CreateOrderTxReq()
            tp_req.MarketIndex = self.market_id
            tp_req.ClientOrderIndex = 0  # SDK will auto-generate for grouped orders
            tp_req.BaseAmount = 0  # SDK inherits from entry order in group
            tp_req.Price = tp_price_scaled
            tp_req.IsAsk = 0 if is_ask else 1  # Opposite side to close
            tp_req.Type = lighter.SignerClient.ORDER_TYPE_TAKE_PROFIT
            tp_req.TimeInForce = lighter.SignerClient.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL  # Take profit uses IOC
            tp_req.ReduceOnly = 1  # Reduce-only to close position
            tp_req.TriggerPrice = tp_price_scaled
            tp_req.OrderExpiry = lighter.SignerClient.DEFAULT_28_DAY_ORDER_EXPIRY
            orders.append(tp_req)
            
            # Create grouped order (TRUE OCO at exchange level)
            logger.info(f"📦 Creating grouped order with 3 orders (Entry + SL/TP OCO)")
            tx, tx_hash, err = await self.client.signer_client.create_grouped_orders(
                grouping_type=lighter.SignerClient.GROUPING_TYPE_ONE_TRIGGERS_A_ONE_CANCELS_THE_OTHER,
                orders=orders
            )
            
            if err:
                logger.error(f"❌ Failed to create grouped order: {err}")
                return None
            
            # Store group info
            group_id = str(tx_hash) if tx_hash else f"group_{self.order_counter}"
            self.active_groups[group_id] = {
                'group_id': group_id,
                'tx_hash': str(tx_hash),
                'symbol': symbol,
                'side': side,
                'size': float(size),
                'entry_price': float(entry_price),
                'sl_price': float(sl_price),
                'tp_price': float(tp_price),
                'entry_order_id': entry_req.ClientOrderIndex,
                'sl_order_id': sl_req.ClientOrderIndex,
                'tp_order_id': tp_req.ClientOrderIndex,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'status': 'active'
            }
            
            logger.info(f"✅ NATIVE OCO order created!")
            logger.info(f"   TX Hash: {tx_hash}")
            logger.info(f"   Entry Order ID: {entry_req.ClientOrderIndex}")
            logger.info(f"   SL Order ID: {sl_req.ClientOrderIndex}")
            logger.info(f"   TP Order ID: {tp_req.ClientOrderIndex}")
            logger.info(f"   Exchange will handle all OCO logic automatically!")
            
            return str(tx_hash)
            
        except Exception as e:
            logger.error(f"❌ Failed to place native OCO order: {e}")
            logger.exception(e)
            return None
    
    async def get_active_orders(self) -> List[Dict[str, Any]]:
        """
        Get all active orders using native SDK API
        Replaces manual polling with efficient batch retrieval
        
        Returns:
            List of active orders
        """
        try:
            # Get authentication token (SDK returns tuple: (token, expiry_time))
            auth_result = self.client.signer_client.create_auth_token_with_expiry()
            # Extract token string from tuple
            auth_token = auth_result[0] if isinstance(auth_result, tuple) else str(auth_result)
            
            # Use native SDK method to get all active orders
            response = await self.order_api.account_active_orders(
                account_index=self.client.account_index,
                market_id=self.market_id,
                authorization=auth_token
            )
            
            if not response or not response.data:
                return []
            
            # Convert to dict format
            orders = []
            for order in response.data:
                orders.append({
                    'order_id': order.id,
                    'client_order_id': order.client_order_id,
                    'market_id': order.market_id,
                    'side': 'buy' if not order.is_ask else 'sell',
                    'type': self._order_type_to_string(order.order_type),
                    'price': order.price,
                    'trigger_price': order.trigger_price if hasattr(order, 'trigger_price') else None,
                    'size': order.size,
                    'filled': order.filled_amount if hasattr(order, 'filled_amount') else 0,
                    'status': order.status,
                    'reduce_only': order.reduce_only if hasattr(order, 'reduce_only') else False,
                    'created_at': order.created_at if hasattr(order, 'created_at') else None
                })
            
            return orders
            
        except Exception as e:
            logger.error(f"❌ Failed to get active orders: {e}")
            return []
    
    async def get_account_position(self) -> Optional[Dict[str, Any]]:
        """
        Get current account position using native SDK
        Replaces manual position tracking
        
        Returns:
            Account position data including balance, positions, PnL
        """
        try:
            # Get account data with authentication
            auth_token = self.client.signer_client.create_auth_token_with_expiry()
            
            response = await self.account_api.account(
                by='account_index',
                value=str(self.client.account_index)
            )
            
            if not response or not response.data:
                return None
            
            account = response.data[0] if isinstance(response.data, list) else response.data
            
            # Extract position info
            position_data = {
                'account_index': self.client.account_index,
                'balance': account.balance if hasattr(account, 'balance') else 0,
                'available_balance': account.available_balance if hasattr(account, 'available_balance') else 0,
                'margin_used': account.margin_used if hasattr(account, 'margin_used') else 0,
                'unrealized_pnl': account.unrealized_pnl if hasattr(account, 'unrealized_pnl') else 0,
                'positions': []
            }
            
            # Get market positions
            if hasattr(account, 'positions') and account.positions:
                for pos in account.positions:
                    if pos.market_id == self.market_id:
                        position_data['positions'].append({
                            'market_id': pos.market_id,
                            'side': 'long' if pos.size > 0 else 'short',
                            'size': abs(pos.size),
                            'entry_price': pos.entry_price if hasattr(pos, 'entry_price') else 0,
                            'mark_price': pos.mark_price if hasattr(pos, 'mark_price') else 0,
                            'unrealized_pnl': pos.unrealized_pnl if hasattr(pos, 'unrealized_pnl') else 0,
                            'leverage': pos.leverage if hasattr(pos, 'leverage') else 1
                        })
            
            return position_data
            
        except Exception as e:
            logger.error(f"❌ Failed to get account position: {e}")
            logger.exception(e)
            return None
    
    async def cancel_order(self, order_id: int) -> bool:
        """
        Cancel single order using native SDK
        
        Args:
            order_id: Client order ID
            
        Returns:
            True if successful
        """
        try:
            tx, tx_hash, err = await self.client.signer_client.cancel_order(
                market_index=self.market_id,
                order_index=order_id
            )
            
            if err:
                logger.error(f"❌ Failed to cancel order {order_id}: {err}")
                return False
            
            logger.info(f"✅ Order cancelled: {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to cancel order: {e}")
            return False
    
    async def cancel_all_orders(self) -> bool:
        """
        Cancel all orders using native SDK bulk cancellation
        Much more efficient than cancelling individually
        
        Returns:
            True if successful
        """
        try:
            logger.info("🗑️  Cancelling all orders...")
            
            tx, tx_hash, err = await self.client.signer_client.cancel_all_orders(
                time_in_force=lighter.SignerClient.CANCEL_ALL_TIF_IMMEDIATE,
                time=int(datetime.now(timezone.utc).timestamp())
            )
            
            if err:
                logger.error(f"❌ Failed to cancel all orders: {err}")
                return False
            
            logger.info(f"✅ All orders cancelled (TX: {tx_hash})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to cancel all orders: {e}")
            return False
    
    async def update_leverage(self, leverage: int, margin_mode: str = 'cross') -> bool:
        """
        Update leverage using native SDK
        
        Args:
            leverage: Leverage multiplier (1-50)
            margin_mode: 'cross' or 'isolated'
            
        Returns:
            True if successful
        """
        try:
            mode = (lighter.SignerClient.CROSS_MARGIN_MODE 
                   if margin_mode.lower() == 'cross' 
                   else lighter.SignerClient.ISOLATED_MARGIN_MODE)
            
            tx, tx_hash, err = await self.client.signer_client.update_leverage(
                market_index=self.market_id,
                margin_mode=mode,
                leverage=leverage
            )
            
            if err:
                logger.error(f"❌ Failed to update leverage: {err}")
                return False
            
            logger.info(f"✅ Leverage updated: {leverage}x ({margin_mode})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update leverage: {e}")
            return False
    
    def _order_type_to_string(self, order_type: int) -> str:
        """Convert order type constant to string"""
        type_map = {
            lighter.SignerClient.ORDER_TYPE_LIMIT: 'limit',
            lighter.SignerClient.ORDER_TYPE_MARKET: 'market',
            lighter.SignerClient.ORDER_TYPE_STOP_LOSS: 'stop_loss',
            lighter.SignerClient.ORDER_TYPE_TAKE_PROFIT: 'take_profit',
            lighter.SignerClient.ORDER_TYPE_STOP_LOSS_LIMIT: 'stop_loss_limit',
            lighter.SignerClient.ORDER_TYPE_TAKE_PROFIT_LIMIT: 'take_profit_limit'
        }
        return type_map.get(order_type, 'unknown')
    
    def get_active_groups(self) -> Dict[str, Dict[str, Any]]:
        """Get all active order groups"""
        return self.active_groups
    
    def get_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        """Get specific order group by ID"""
        return self.active_groups.get(group_id)


# Convenience function for backward compatibility
async def create_oco_order(client, symbol: str, side: str, size: Decimal,
                          entry_price: Decimal, sl_price: Decimal, tp_price: Decimal) -> Optional[str]:
    """
    Quick function to create OCO order with native SDK
    
    Args:
        client: LighterClient instance
        symbol: Trading pair
        side: 'buy' or 'sell'
        size: Position size
        entry_price: Entry price
        sl_price: Stop-loss price
        tp_price: Take-profit price
        
    Returns:
        Transaction hash
    """
    manager = LighterOrderManagerV2(client)
    return await manager.place_oco_order_native(symbol, side, size, entry_price, sl_price, tp_price)
