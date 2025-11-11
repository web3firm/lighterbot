"""
Market data module using official Lighter SDK
"""
import asyncio
from typing import Dict, Any, Optional, List
from lighter_client import get_client
from config import settings
from logger import logger


class MarketData:
    """Market data manager for fetching prices, orderbook, and funding rates"""
    
    def __init__(self):
        self._price_cache = {}
        self._orderbook_cache = {}
        self.market_id = settings.trading_market_id
    
    async def get_orderbook(self, market_id: Optional[int] = None) -> Dict[str, Any]:
        """Get current orderbook"""
        try:
            client = await get_client()
            m_id = market_id if market_id is not None else self.market_id
            data = await client.get_order_book_details(m_id)
            if data:
                self._orderbook_cache[m_id] = data
                logger.debug(f"Updated orderbook for market {m_id}")
            return data
        except Exception as e:
            logger.error(f"Error fetching orderbook: {e}")
            return self._orderbook_cache.get(market_id or self.market_id, {})
    
    async def get_all_orderbooks(self) -> Dict[str, Any]:
        """Get all orderbooks"""
        try:
            client = await get_client()
            data = await client.get_order_books()
            logger.debug("Updated all orderbooks")
            return data
        except Exception as e:
            logger.error(f"Error fetching all orderbooks: {e}")
            return {}
    
    async def get_best_bid_ask(self, market_id: Optional[int] = None) -> tuple[float, float]:
        """
        Get best bid and ask prices
        
        NOTE: SDK returns last_trade_price as float directly from get_order_book_details
        Orderbooks (bids/asks arrays) may be empty, so we use last_trade_price as fallback
        """
        try:
            m_id = market_id if market_id is not None else self.market_id
            
            # Get order book details which includes last_trade_price
            orderbook = await self.get_orderbook(m_id)
            
            # Parse orderbook structure from SDK
            bids = orderbook.get("bids", [])
            asks = orderbook.get("asks", [])
            
            if bids and asks:
                # SDK returns price as string with decimal point
                # Example: {"price": "50000.00", "remaining_base_amount": "100.000000"}
                # No need to parse - just convert to float directly
                best_bid = float(bids[0].get("price", "0"))
                best_ask = float(asks[0].get("price", "0"))
                return best_bid, best_ask
            
            # Fallback: Use last_trade_price from orderbook details
            last_price = orderbook.get("last_trade_price", 0)
            if last_price and float(last_price) > 0:
                last_price = float(last_price)
                # Estimate spread as 0.02% (2 basis points)
                spread = last_price * 0.0002
                return last_price - spread/2, last_price + spread/2
            
            # Last fallback: Use recent trades to estimate bid/ask
            trades = await self.get_recent_trades(m_id, limit=10)
            if trades:
                # SDK returns price as float or string in trades
                recent_prices = []
                for t in trades:
                    price = t.get('price', 0)
                    if price:
                        try:
                            price_float = float(price)
                            if price_float > 0:
                                recent_prices.append(price_float)
                        except (ValueError, TypeError):
                            continue
                
                if recent_prices:
                    mid_price = sum(recent_prices) / len(recent_prices)
                    # Estimate spread as 0.02% (2 basis points)
                    spread = mid_price * 0.0002
                    return mid_price - spread/2, mid_price + spread/2
            
            logger.debug("No orderbook or trades available")
            return 0.0, 0.0
            
        except Exception as e:
            logger.error(f"Error getting best bid/ask: {e}")
            return 0.0, 0.0
    
    async def get_mid_price(self, market_id: Optional[int] = None) -> float:
        """Get mid price - uses recent trades if order book is empty"""
        best_bid, best_ask = await self.get_best_bid_ask(market_id)
        if best_bid > 0 and best_ask > 0:
            return (best_bid + best_ask) / 2.0
        
        # If no bid/ask, return 0 (get_best_bid_ask already tried trades fallback)
        return 0.0
    
    async def get_current_price(self, market_id: Optional[int] = None) -> float:
        """Get current mid price (same as get_mid_price)"""
        return await self.get_mid_price(market_id)
    
    async def get_recent_trades(self, market_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
        """Get recent trades"""
        try:
            client = await get_client()
            m_id = market_id if market_id is not None else self.market_id
            trades = await client.get_recent_trades(m_id, limit)
            logger.debug(f"Fetched {len(trades)} recent trades")
            return trades
        except Exception as e:
            logger.error(f"Error fetching recent trades: {e}")
            return []
    
    async def get_candlesticks(
        self, 
        market_id: Optional[int] = None, 
        resolution: str = "1h", 
        limit: int = 100
    ) -> List[Dict]:
        """
        Get candlestick data
        
        Args:
            market_id: Market ID (default: from settings)
            resolution: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles
        """
        try:
            client = await get_client()
            m_id = market_id if market_id is not None else self.market_id
            candles = await client.get_candlesticks(m_id, resolution, limit)
            logger.debug(f"Fetched {len(candles)} candlesticks")
            return candles
        except Exception as e:
            logger.error(f"Error fetching candlesticks: {e}")
            return []
    
    async def get_funding_rate(self, market_id: Optional[int] = None) -> Dict[str, Any]:
        """Get current funding rate"""
        try:
            client = await get_client()
            m_id = market_id if market_id is not None else self.market_id
            fundings = await client.get_funding_rates(m_id)
            
            if fundings:
                # Return most recent funding rate
                latest = fundings[0]
                logger.debug(f"Fetched funding rate: {latest}")
                return latest
            return {}
        except Exception as e:
            logger.error(f"Error fetching funding rate: {e}")
            return {}
    
    async def get_funding_history(self, market_id: Optional[int] = None, limit: int = 10) -> List[Dict]:
        """Get historical funding rates"""
        try:
            client = await get_client()
            m_id = market_id if market_id is not None else self.market_id
            fundings = await client.get_funding_rates(m_id)
            logger.debug(f"Fetched {len(fundings)} funding rates")
            return fundings[:limit]
        except Exception as e:
            logger.error(f"Error fetching funding history: {e}")
            return []
    
    async def calculate_funding_cost(
        self, 
        position_size: float, 
        hours: float = 8.0,
        market_id: Optional[int] = None
    ) -> float:
        """
        Calculate estimated funding cost for holding a position
        
        Args:
            position_size: Position size in base units (positive for long, negative for short)
            hours: Number of hours to hold position
            market_id: Market ID
            
        Returns:
            Estimated funding cost (negative means you pay, positive means you receive)
        """
        try:
            funding_data = await self.get_funding_rate(market_id)
            if not funding_data:
                return 0.0
            
            # Get funding rate (usually per 8 hours)
            funding_rate = float(funding_data.get("fundingRate", 0))
            
            # Get current price
            mark_price = await self.get_current_price(market_id)
            if mark_price == 0:
                return 0.0
            
            # Calculate position value
            position_value = abs(position_size) * mark_price
            
            # Calculate funding cost (funding is applied every 8 hours)
            funding_cost = position_value * funding_rate * (hours / 8.0)
            
            # If long and rate is positive, you pay (negative cost)
            # If short and rate is positive, you receive (positive cost)
            if position_size > 0:
                return -funding_cost
            else:
                return funding_cost
        except Exception as e:
            logger.error(f"Error calculating funding cost: {e}")
            return 0.0
    
    async def get_market_summary(self, market_id: Optional[int] = None) -> Dict[str, Any]:
        """Get comprehensive market summary"""
        try:
            m_id = market_id if market_id is not None else self.market_id
            
            # Fetch multiple data points in parallel
            orderbook_task = self.get_orderbook(m_id)
            trades_task = self.get_recent_trades(m_id, limit=10)
            funding_task = self.get_funding_rate(m_id)
            
            orderbook, recent_trades, funding = await asyncio.gather(
                orderbook_task, trades_task, funding_task
            )
            
            best_bid, best_ask = await self.get_best_bid_ask(m_id)
            mid_price = (best_bid + best_ask) / 2.0 if best_bid > 0 and best_ask > 0 else 0.0
            
            summary = {
                "market_id": m_id,
                "mid_price": mid_price,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": best_ask - best_bid if best_ask > 0 and best_bid > 0 else 0.0,
                "spread_bps": ((best_ask - best_bid) / mid_price * 10000) if mid_price > 0 else 0.0,
                "recent_trades_count": len(recent_trades),
                "funding_rate": funding.get("fundingRate", 0) if funding else 0,
                "orderbook_depth": {
                    "bids": len(orderbook.get("bids", [])),
                    "asks": len(orderbook.get("asks", []))
                }
            }
            
            logger.info(f"Market summary: {summary}")
            return summary
        except Exception as e:
            logger.error(f"Error getting market summary: {e}")
            return {}
