"""
Order management module using official Lighter SDK
"""
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from lighter_client import get_client
from config import settings
from logger import logger


@dataclass
class Order:
    """Order data structure"""
    order_index: int
    market_id: int
    client_order_index: int
    side: str  # "buy" or "sell"
    size: float
    price: Optional[float]
    order_type: str
    status: str
    filled_size: float = 0.0
    average_fill_price: Optional[float] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'Order':
        """Create Order from API response"""
        return cls(
            order_index=int(data.get("orderIndex", data.get("order_index", 0))),
            market_id=int(data.get("marketId", data.get("market_id", 0))),
            client_order_index=int(data.get("clientOrderIndex", data.get("client_order_index", 0))),
            side="buy" if not data.get("isAsk", data.get("is_ask", False)) else "sell",
            size=float(data.get("baseAmount", data.get("base_amount", 0))),
            price=float(data.get("price", 0)) if data.get("price") else None,
            order_type=data.get("orderType", data.get("order_type", "limit")),
            status=data.get("status", "active"),
            filled_size=float(data.get("filledAmount", data.get("filled_amount", 0))),
            average_fill_price=float(data.get("avgFillPrice", 0)) if data.get("avgFillPrice") else None,
            created_at=datetime.now()
        )


@dataclass
class Position:
    """Position data structure"""
    market_id: int
    size: float  # Positive for long, negative for short
    entry_price: float
    mark_price: float
    liquidation_price: Optional[float]
    unrealized_pnl: float
    margin: float
    leverage: float
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'Position':
        """Create Position from API response"""
        size = float(data.get("size", data.get("base_amount", 0)))
        
        return cls(
            market_id=int(data.get("marketId", data.get("market_id", 0))),
            size=size,
            entry_price=float(data.get("entryPrice", data.get("entry_price", 0))),
            mark_price=float(data.get("markPrice", data.get("mark_price", 0))),
            liquidation_price=float(data.get("liquidationPrice")) if data.get("liquidationPrice") else None,
            unrealized_pnl=float(data.get("unrealizedPnl", data.get("unrealized_pnl", 0))),
            margin=float(data.get("margin", 0)),
            leverage=float(data.get("leverage", 1))
        )
    
    @property
    def is_long(self) -> bool:
        """Check if position is long"""
        return self.size > 0
    
    @property
    def is_short(self) -> bool:
        """Check if position is short"""
        return self.size < 0
    
    @property
    def pnl_percentage(self) -> float:
        """Calculate PnL as percentage of margin"""
        if self.margin > 0:
            return (self.unrealized_pnl / self.margin) * 100
        return 0.0
    
    @property
    def is_open(self) -> bool:
        """Check if position is open"""
        return abs(self.size) > 0


class OrderManager:
    """Manager for order operations and position tracking"""
    
    def __init__(self):
        self._open_orders: Dict[int, Order] = {}
        self._positions: Dict[int, Position] = {}
        self._next_client_order_index = 1
        self.market_id = settings.trading_market_id
    
    def _get_next_client_order_index(self) -> int:
        """Get next client order index"""
        idx = self._next_client_order_index
        self._next_client_order_index += 1
        return idx
    
    async def place_limit_order(
        self,
        side: str,
        size: float,
        price: float,
        market_id: Optional[int] = None,
        reduce_only: bool = False
    ) -> Optional[Order]:
        """
        Place a limit order
        
        Args:
            side: "buy" or "sell"
            size: Order size in base units (e.g., 0.1 BTC)
            price: Limit price
            market_id: Market ID (default from settings)
            reduce_only: Only reduce position
        """
        try:
            client = await get_client()
            m_id = market_id if market_id is not None else self.market_id
            client_order_idx = self._get_next_client_order_index()
            
            # Convert to smallest units (SDK expects integers)
            # Assuming 6 decimals for size and 2 for price (adjust as needed)
            base_amount = int(size * 1_000_000)
            price_int = int(price * 100)
            
            is_ask = (side.lower() == "sell")
            
            result, tx_hash, error = await client.create_limit_order(
                market_index=m_id,
                client_order_index=client_order_idx,
                base_amount=base_amount,
                price=price_int,
                is_ask=is_ask,
                reduce_only=reduce_only
            )
            
            if error:
                logger.error(f"Error placing limit order: {error}")
                return None
            
            # Create order object
            order = Order(
                order_index=0,  # Will be updated when we fetch active orders
                market_id=m_id,
                client_order_index=client_order_idx,
                side=side,
                size=size,
                price=price,
                order_type="limit",
                status="submitted",
                filled_size=0.0,
                created_at=datetime.now()
            )
            
            self._open_orders[client_order_idx] = order
            logger.info(f"Placed limit order: {side} {size} @ {price}, tx: {tx_hash}")
            return order
            
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return None
    
    async def place_market_order(
        self,
        side: str,
        size: float,
        max_slippage_pct: float = 1.0,
        market_id: Optional[int] = None,
        reduce_only: bool = False
    ) -> Optional[Order]:
        """
        Place a market order
        
        Args:
            side: "buy" or "sell"
            size: Order size in base units
            max_slippage_pct: Maximum slippage percentage (e.g., 1.0 for 1%)
            market_id: Market ID
            reduce_only: Only reduce position
        """
        try:
            client = await get_client()
            m_id = market_id if market_id is not None else self.market_id
            client_order_idx = self._get_next_client_order_index()
            
            # Get current market price to calculate worst acceptable price
            from market_data import MarketData
            market_data = MarketData()
            current_price = await market_data.get_current_price(m_id)
            
            if current_price == 0:
                logger.error("Cannot get current price for market order")
                return None
            
            # Calculate worst acceptable execution price
            if side.lower() == "buy":
                worst_price = current_price * (1 + max_slippage_pct / 100)
            else:
                worst_price = current_price * (1 - max_slippage_pct / 100)
            
            # Convert to smallest units
            base_amount = int(size * 1_000_000)
            avg_execution_price = int(worst_price * 100)
            is_ask = (side.lower() == "sell")
            
            result, tx_hash, error = await client.create_market_order(
                market_index=m_id,
                client_order_index=client_order_idx,
                base_amount=base_amount,
                avg_execution_price=avg_execution_price,
                is_ask=is_ask,
                reduce_only=reduce_only
            )
            
            if error:
                logger.error(f"Error placing market order: {error}")
                return None
            
            order = Order(
                order_index=0,
                market_id=m_id,
                client_order_index=client_order_idx,
                side=side,
                size=size,
                price=None,
                order_type="market",
                status="submitted",
                filled_size=0.0,
                created_at=datetime.now()
            )
            
            logger.info(f"Placed market order: {side} {size}, tx: {tx_hash}")
            return order
            
        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return None
    
    async def cancel_order(self, order_index: int, market_id: Optional[int] = None) -> bool:
        """Cancel a specific order"""
        try:
            client = await get_client()
            m_id = market_id if market_id is not None else self.market_id
            
            result, tx_hash, error = await client.cancel_order(
                market_index=m_id,
                order_index=order_index
            )
            
            if error:
                logger.error(f"Error cancelling order {order_index}: {error}")
                return False
            
            # Remove from local cache
            for client_idx, order in list(self._open_orders.items()):
                if order.order_index == order_index:
                    del self._open_orders[client_idx]
                    break
            
            logger.info(f"Cancelled order {order_index}, tx: {tx_hash}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    async def cancel_all_orders(self) -> bool:
        """Cancel all open orders"""
        try:
            client = await get_client()
            
            result, tx_hash, error = await client.cancel_all_orders()
            
            if error:
                logger.error(f"Error cancelling all orders: {error}")
                return False
            
            self._open_orders.clear()
            logger.info(f"Cancelled all orders, tx: {tx_hash}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            return False
    
    async def get_active_orders(self, market_id: Optional[int] = None) -> List[Order]:
        """Get all active orders"""
        try:
            client = await get_client()
            m_id = market_id if market_id is not None else self.market_id
            
            orders_data = await client.get_active_orders(m_id)
            
            orders = []
            for order_data in orders_data:
                order = Order.from_api_response(order_data)
                orders.append(order)
                
                # Update local cache
                self._open_orders[order.client_order_index] = order
            
            logger.debug(f"Fetched {len(orders)} active orders")
            return orders
            
        except Exception as e:
            logger.error(f"Error getting active orders: {e}")
            return []
    
    async def get_positions(self) -> List[Position]:
        """Get all positions"""
        try:
            client = await get_client()
            positions_data = await client.get_positions()
            
            positions = []
            for pos_data in positions_data:
                position = Position.from_api_response(pos_data)
                if position.is_open:
                    positions.append(position)
                    self._positions[position.market_id] = position
            
            logger.debug(f"Fetched {len(positions)} positions")
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    async def get_position(self, market_id: Optional[int] = None) -> Optional[Position]:
        """Get position for specific market"""
        m_id = market_id if market_id is not None else self.market_id
        positions = await self.get_positions()
        
        for pos in positions:
            if pos.market_id == m_id:
                return pos
        
        return None
    
    async def close_position(
        self,
        market_id: Optional[int] = None,
        use_market_order: bool = True
    ) -> bool:
        """Close an open position"""
        try:
            position = await self.get_position(market_id)
            if not position or not position.is_open:
                logger.warning("No open position to close")
                return False
            
            # Determine side to close (opposite of current position)
            close_side = "sell" if position.is_long else "buy"
            close_size = abs(position.size)
            
            if use_market_order:
                order = await self.place_market_order(
                    side=close_side,
                    size=close_size,
                    market_id=market_id,
                    reduce_only=True
                )
            else:
                # Use limit order at current mid price
                from market_data import MarketData
                market_data = MarketData()
                mid_price = await market_data.get_mid_price(market_id)
                
                order = await self.place_limit_order(
                    side=close_side,
                    size=close_size,
                    price=mid_price,
                    market_id=market_id,
                    reduce_only=True
                )
            
            if order:
                logger.info(f"Closed position: {close_side} {close_size}")
                return True
            else:
                logger.error("Failed to place close order")
                return False
                
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account balance and margin info"""
        try:
            client = await get_client()
            account_info = await client.get_account_info()
            logger.debug(f"Account info: {account_info}")
            return account_info
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return {}
