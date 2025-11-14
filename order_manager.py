"""
Order management module using official Lighter SDK
"""
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from lighter_client import get_client
from config import settings
from logger import logger
from utils import market_metadata, order_indexer, retry_async
from utils import lighter_api_breaker, circuit_breaker


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
        """Create Position from API response
        
        API Response format:
        {
            "market_id": 0,
            "symbol": "ETH",
            "position": "0.0200",  # Size in coins (negative for short, positive for long)
            "avg_entry_price": "3431.30",
            "position_value": "68.516000",  # Notional value
            "unrealized_pnl": "0.110100",
            "initial_margin_fraction": "20.00",  # e.g., 20% = 5x leverage
            "liquidation_price": "6509.64678853755"
        }
        """
        # Parse size from different possible fields
        size = float(data.get("position", data.get("size", data.get("base_amount", 0))))
        
        # Apply sign for short positions (API uses sign field)
        sign = int(data.get("sign", 1))
        if sign < 0 and size > 0:
            size = -size  # Make negative for short
        
        # Parse entry price
        entry_price = float(data.get("avg_entry_price", data.get("entryPrice", data.get("entry_price", 0))))
        
        # Calculate mark price from position_value if available, otherwise use entry_price
        position_value = float(data.get("position_value", 0))
        if abs(size) > 0 and position_value > 0:
            mark_price = abs(position_value) / abs(size)
        else:
            mark_price = float(data.get("mark_price", data.get("markPrice", entry_price)))
        
        # Parse leverage from initial_margin_fraction (e.g., "20.00" = 20% = 5x leverage)
        initial_margin_fraction = float(data.get("initial_margin_fraction", 20.0))  # Default 20% = 5x
        leverage = 100.0 / initial_margin_fraction if initial_margin_fraction > 0 else 5.0
        
        # Calculate margin (collateral) = position_value / leverage
        margin = abs(position_value) / leverage if leverage > 0 else abs(position_value)
        
        return cls(
            market_id=int(data.get("market_id", data.get("marketId", 0))),
            size=size,
            entry_price=entry_price,
            mark_price=mark_price,
            liquidation_price=float(data.get("liquidation_price", data.get("liquidationPrice", 0))) if data.get("liquidation_price") or data.get("liquidationPrice") else None,
            unrealized_pnl=float(data.get("unrealized_pnl", data.get("unrealizedPnl", 0))),
            margin=margin,
            leverage=leverage
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
        self.market_id = settings.trading_market_id
        # Removed: self._client_order_index_counter - now using global order_indexer
        self._order_semaphore = asyncio.Semaphore(settings.max_open_orders)
        
        # Account info cache (60 second refresh to prevent rate limits)
        self.account_info_cache = None
        self.account_info_cache_time = datetime.now() - timedelta(seconds=100)
        
        # OCO order tracking (exchange-managed TP/SL)
        self.oco_orders: Dict[str, Dict] = {}  # position_id -> {tp_order_id, sl_order_id, tp_price, sl_price}
        self.portfolio_oco_active = False  # Track if portfolio-level OCO is active
        self.portfolio_oco_ids: Dict[str, any] = {}  # {'tp_index': X, 'sl_index': Y, 'tp_price': $, 'sl_price': $}
        self.local_positions: List[Dict] = []  # Track positions locally for immediate OCO calculation
        
        # Hybrid mode: Track which positions have bot taking over
        self.trailing_active: Dict[str, bool] = {}  # position_id -> is_trailing_active
    
    async def _get_next_client_order_index(self) -> int:
        """Get next client order index using persistent indexer"""
        return await order_indexer.get_next()
    
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
            
            # SAFETY CHECK: Verify market is active before placing order
            if not market_metadata.is_market_active(m_id):
                market_info = market_metadata.get_market(m_id)
                status = market_info.get("status", "unknown")
                logger.error(f"Cannot place order on inactive market {m_id} (status: {status})")
                return None
            
            # SAFETY CHECK: Verify size meets minimum requirements
            min_size = market_metadata.get_min_order_size(m_id)
            if size < min_size:
                logger.error(f"Order size {size} below minimum {min_size} for market {m_id}")
                return None
            
            client_order_idx = await self._get_next_client_order_index()
            
            # Convert using market metadata (no more hardcoded decimals!)
            base_amount = market_metadata.to_base_amount(size, m_id)
            price_int = market_metadata.to_price_int(price, m_id)
            
            # Check dry run mode
            if settings.dry_run:
                logger.info(f"[DRY RUN] Would place limit order: {side} {size} @ {price}")
                return None
            
            is_ask = (side.lower() == "sell")
            
            # Use semaphore to limit concurrent orders
            async with self._order_semaphore:
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
            
            # SAFETY CHECK: Verify market is active before placing order
            if not market_metadata.is_market_active(m_id):
                market_info = market_metadata.get_market(m_id)
                status = market_info.get("status", "unknown")
                logger.error(f"Cannot place order on inactive market {m_id} (status: {status})")
                return None
            
            # SAFETY CHECK: Verify size meets minimum requirements
            min_size = market_metadata.get_min_order_size(m_id)
            if size < min_size:
                logger.error(f"Order size {size} below minimum {min_size} for market {m_id}")
                return None
            
            client_order_idx = await self._get_next_client_order_index()
            
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
            
            # Convert using market metadata (no more hardcoded decimals!)
            base_amount = market_metadata.to_base_amount(size, m_id)
            avg_execution_price = market_metadata.to_price_int(worst_price, m_id)
            
            # Check dry run mode
            if settings.dry_run:
                logger.info(f"[DRY RUN] Would place market order: {side} {size} @ ~{current_price}")
                return None
            
            is_ask = (side.lower() == "sell")
            
            # Use semaphore to limit concurrent orders
            async with self._order_semaphore:
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
    
    async def place_position_with_oco(
        self,
        side: str,
        size: float,
        entry_price: float,
        tp_pct: float = 3.0,  # FIXED: TP @ +3% (backup after bot trailing)
        sl_pct: float = 2.0,
        market_id: Optional[int] = None
    ) -> tuple[bool, Optional[dict]]:
        """
        PORTFOLIO-LEVEL OCO STRATEGY: Open position + update portfolio OCO
        
        Instead of creating separate OCO for each position (which causes the
        problem of multiple TP/SL levels), we:
        1. Open the position
        2. Calculate average entry of ALL positions
        3. Create ONE OCO for the entire portfolio
        
        This way, +2% PnL on the TOTAL portfolio triggers TP, not per-position.
        
        Args:
            side: "buy" or "sell"
            size: Position size
            entry_price: Entry price (for logging only)
            tp_pct: Take-profit percentage (default 2%)
            sl_pct: Stop-loss percentage (default 2%)
            market_id: Market ID
            
        Returns:
            (success, oco_info_dict)
        """
        try:
            # 1. Open main position first
            position = await self.place_market_order(side, size, market_id=market_id)
            
            if not position:
                logger.error("Failed to open position, skipping OCO setup")
                return False, None
            
            logger.info(f"✅ Position opened: {size:.4f} @ ${entry_price:.2f}")
            
            # 2. Add to local position tracking (for immediate OCO calculation)
            self.local_positions.append({
                'size': size if side == "buy" else -size,  # Positive for long, negative for short
                'entry_price': entry_price,
                'side': side,
                'opened_at': datetime.now()
            })
            
            # 3. Update portfolio-level OCO using local positions
            oco_success = await self.update_portfolio_oco(market_id=market_id, use_local=True)
            
            if not oco_success:
                logger.warning("⚠️ Portfolio OCO update failed - bot will manage exits")
                return True, None
            
            # 3. Return info about portfolio OCO
            oco_info = {
                'tp_price': self.portfolio_oco_ids.get('tp_price', 0),
                'sl_price': self.portfolio_oco_ids.get('sl_price', 0),
                'entry_price': self.portfolio_oco_ids.get('avg_entry', entry_price),
                'size': self.portfolio_oco_ids.get('total_size', size),
                'side': side,
                'created_at': datetime.now(),
                'portfolio_level': True  # Flag to indicate this is portfolio OCO
            }
            
            return True, oco_info
            
        except Exception as e:
            logger.error(f"Error in place_position_with_oco: {e}")
            return False, None
    
    async def cancel_oco_tp(self, position_id: str) -> bool:
        """Cancel TP from OCO (bot taking over with trailing)"""
        try:
            if position_id not in self.oco_orders:
                return False
            
            oco_info = self.oco_orders[position_id]
            tp_order_id = oco_info['tp_order_id']
            
            client = await get_client()
            result, tx_hash, error = await client.cancel_order(
                market_index=self.market_id,
                order_index=tp_order_id
            )
            
            if error:
                logger.error(f"Failed to cancel TP #{tp_order_id}: {error}")
                return False
                
            logger.info(f"🔄 Cancelled OCO TP #{tp_order_id} - Bot trailing active")
            self.trailing_active[position_id] = True
            return True
                
        except Exception as e:
            logger.error(f"Error cancelling OCO TP: {e}")
            return False
    
    async def cancel_oco_sl(self, position_id: str) -> bool:
        """Cancel SL from OCO (when bot closes early)"""
        try:
            if position_id not in self.oco_orders:
                return True
            
            oco_info = self.oco_orders[position_id]
            sl_order_id = oco_info['sl_order_id']
            
            client = await get_client()
            result, tx_hash, error = await client.cancel_order(
                market_index=self.market_id,
                order_index=sl_order_id
            )
            
            if not error:
                logger.info(f"✅ Cancelled OCO SL #{sl_order_id}")
            return True
                
        except Exception as e:
            logger.error(f"Error cancelling OCO SL: {e}")
            return False
    
    async def cleanup_oco(self, position_id: str):
        """Remove OCO tracking after position closes"""
        if position_id in self.oco_orders:
            del self.oco_orders[position_id]
        if position_id in self.trailing_active:
            del self.trailing_active[position_id]
    
    async def update_portfolio_oco(self, market_id: Optional[int] = None, use_local: bool = False) -> bool:
        """
        PORTFOLIO-LEVEL OCO: Cancel old OCO, calculate avg entry, create new OCO
        
        This solves the problem of multiple positions with different entry prices.
        Instead of separate TP/SL for each position, we create ONE OCO based on
        the AVERAGE entry price of all positions.
        
        Args:
            market_id: Market ID
            use_local: Use locally tracked positions instead of API (for immediate updates)
        
        Returns:
            True if OCO created/updated successfully
        """
        try:
            logger.info(f"🔧 update_portfolio_oco() called with use_local={use_local}")
            
            client = await get_client()
            m_id = market_id if market_id is not None else self.market_id
            
            # 1. Get positions (local or from API)
            if use_local and len(self.local_positions) > 0:
                # Use locally tracked positions (immediate after opening)
                positions_data = self.local_positions
                logger.info(f"📊 Using {len(positions_data)} local positions for OCO")
            else:
                # Get from API
                positions = await client.get_positions()
                if not positions or len(positions) == 0:
                    logger.info("No positions, no OCO needed")
                    # Cancel existing portfolio OCO if any
                    if self.portfolio_oco_active:
                        await self._cancel_portfolio_oco()
                    return True
                
                # Convert API positions to our format
                positions_data = [
                    {
                        'size': pos.size,
                        'entry_price': pos.entry_price,
                        'side': 'long' if pos.size > 0 else 'short'
                    }
                    for pos in positions
                ]
            
            # 2. Calculate NET position (longs - shorts) and weighted average entry
            total_value_long = 0.0
            total_size_long = 0.0
            total_value_short = 0.0
            total_size_short = 0.0
            
            for pos in positions_data:
                size = pos['size'] if isinstance(pos['size'], (int, float)) else pos.get('size', 0)
                entry_price = pos['entry_price'] if isinstance(pos.get('entry_price'), (int, float)) else pos.get('entry_price', 0)
                
                if size > 0:  # LONG
                    total_value_long += size * entry_price
                    total_size_long += size
                else:  # SHORT
                    total_value_short += abs(size) * entry_price
                    total_size_short += abs(size)
            
            # Calculate net position
            net_size = total_size_long - total_size_short
            
            if abs(net_size) < 0.001:  # No net position
                logger.warning("Net position size is ~0, skipping OCO")
                return False
            
            # Determine side and calculate weighted average
            if net_size > 0:  # Net LONG
                position_side = "long"
                avg_entry_price = total_value_long / total_size_long if total_size_long > 0 else 0
                total_size = net_size
            else:  # Net SHORT
                position_side = "short"
                avg_entry_price = total_value_short / total_size_short if total_size_short > 0 else 0
                total_size = abs(net_size)
            
            logger.info(f"📊 Portfolio OCO: {len(positions_data)} positions, NET {position_side.upper()} {total_size:.4f}, avg entry=${avg_entry_price:.2f}")
            
            # 3. Calculate TP/SL based on average entry
            leverage = settings.leverage
            tp_pct = 2.0  # +2% PnL
            sl_pct = 2.0  # -2% PnL
            
            price_move_tp = tp_pct / leverage  # 2% PnL = 0.4% price with 5x
            price_move_sl = sl_pct / leverage
            
            if position_side == "long":
                tp_price = avg_entry_price * (1 + price_move_tp / 100)
                sl_price = avg_entry_price * (1 - price_move_sl / 100)
                is_ask = True  # Exit long = SELL
            else:
                tp_price = avg_entry_price * (1 - price_move_tp / 100)
                sl_price = avg_entry_price * (1 + price_move_sl / 100)
                is_ask = False  # Exit short = BUY
            
            logger.info(f"📍 Portfolio OCO: Avg Entry=${avg_entry_price:.2f} | TP=${tp_price:.2f} (+{tp_pct}%) | SL=${sl_price:.2f} (-{sl_pct}%)")
            
            # 4. Cancel existing portfolio OCO if any
            if self.portfolio_oco_active:
                await self._cancel_portfolio_oco()
            
            # 5. Convert to exchange format
            base_amount = market_metadata.to_base_amount(total_size, m_id)
            tp_price_int = market_metadata.to_price_int(tp_price, m_id)
            sl_price_int = market_metadata.to_price_int(sl_price, m_id)
            
            # 6. Create new portfolio OCO (must use client_order_index=0 for OCO)
            logger.info(f"📤 Creating OCO orders: TP={tp_price_int}, SL={sl_price_int}, base={base_amount}, is_ask={is_ask}")
            
            create_order_obj, tx_hash_obj, error_str = await client.create_oco_orders(
                market_index=m_id,
                client_order_index_tp=0,  # API requires 0 (nil) for OCO orders
                client_order_index_sl=0,  # API requires 0 (nil) for OCO orders
                base_amount=base_amount,
                tp_price=tp_price_int,
                sl_price=sl_price_int,
                tp_trigger=tp_price_int,
                sl_trigger=sl_price_int,
                is_ask=is_ask,
                reduce_only=True
            )
            
            logger.info(f"📥 OCO API Response: create_order={create_order_obj}, tx_hash={tx_hash_obj}, error={error_str}")
            
            if error_str:
                logger.error(f"❌ Portfolio OCO creation failed: {error_str}")
                return False
            
            # 7. Track portfolio OCO
            self.portfolio_oco_active = True
            self.portfolio_oco_ids = {
                'tp_price': tp_price,
                'sl_price': sl_price,
                'avg_entry': avg_entry_price,
                'total_size': total_size
            }
            
            logger.info(f"✅ Portfolio OCO Active: TP @ ${tp_price:.2f}, SL @ ${sl_price:.2f} for {total_size:.4f} size")
            return True
            
        except Exception as e:
            logger.error(f"Error updating portfolio OCO: {e}")
            return False
    
    async def _cancel_portfolio_oco(self) -> bool:
        """Cancel ALL existing orders (including portfolio OCO)"""
        try:
            if not self.portfolio_oco_active:
                return True
            
            logger.info(f"🗑️ Cancelling all orders before creating new OCO")
            success = await self.cancel_all_orders()
            
            self.portfolio_oco_active = False
            self.portfolio_oco_ids = {}
            
            if success:
                logger.info("✅ All orders cancelled successfully")
            else:
                logger.warning("⚠️ Some orders may not have been cancelled")
                
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling portfolio OCO: {e}")
            return False
    
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

    async def place_oco(
        self,
        side: str,
        size: float,
        tp_price: float,
        sl_price: float,
        sl_trigger: float,
        market_id: Optional[int] = None,
    ) -> bool:
        """Place an OCO order composed of TP and SL limits."""
        try:
            client = await get_client()
            m_id = market_id if market_id is not None else self.market_id
            is_ask = (side.lower() == "sell")
            base_amount = market_metadata.to_base_amount(size, m_id)
            tp_price_int = market_metadata.to_price_int(tp_price, m_id)
            sl_price_int = market_metadata.to_price_int(sl_price, m_id)
            sl_trigger_int = market_metadata.to_price_int(sl_trigger, m_id)

            if settings.dry_run:
                logger.info(f"[DRY RUN] Would place OCO ({side}) size={size} TP={tp_price} SL={sl_price}@{sl_trigger}")
                return True

            # Issue distinct client order indices
            coi_tp = await self._get_next_client_order_index()
            coi_sl = await self._get_next_client_order_index()

            async with self._order_semaphore:
                _tx, tx_hash, error = await client.create_oco_orders(
                    market_index=m_id,
                    client_order_index_tp=coi_tp,
                    client_order_index_sl=coi_sl,
                    base_amount=base_amount,
                    tp_price=tp_price_int,
                    sl_price=sl_price_int,
                    sl_trigger=sl_trigger_int,
                    tp_trigger=tp_price_int,  # trigger equals tp price for limit TP
                    is_ask=is_ask,
                    reduce_only=True,
                )

            if error:
                logger.error(f"Error placing OCO orders: {error}")
                return False

            logger.info(f"Placed OCO orders tx: {tx_hash}")
            return True
        except Exception as e:
            logger.error(f"Error placing OCO: {e}")
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
        """Get account balance and margin info with 60-second caching"""
        try:
            # Check cache (60 seconds)
            now = datetime.now()
            if self.account_info_cache and (now - self.account_info_cache_time).total_seconds() < 60:
                return self.account_info_cache
            
            # Fetch fresh data
            client = await get_client()
            account_info = await client.get_account_info()
            
            # Update cache
            self.account_info_cache = account_info
            self.account_info_cache_time = now
            
            logger.debug(f"Account info: {account_info} (cached for 60s)")
            return account_info
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            # Return cached data on error if available
            if self.account_info_cache:
                logger.warning("Using cached account info due to API error")
                return self.account_info_cache
            return {}
