"""
Market Data Module - Native SDK Implementation
Uses CandlestickApi and OrderApi instead of manual REST calls
Replaces 100+ lines with ~80 lines of efficient SDK calls
"""

import logging
import lighter
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import time

logger = logging.getLogger(__name__)


class MarketData:
    """
    Native SDK-based market data provider
    Efficient data retrieval using SDK's built-in methods
    """
    
    def __init__(self, api_client):
        """
        Initialize market data provider
        
        Args:
            api_client: Lighter SDK ApiClient instance
        """
        self.candle_api = lighter.CandlestickApi(api_client)
        self.order_api = lighter.OrderApi(api_client)
        self.funding_api = lighter.FundingApi(api_client)
        
        # Cache for reducing API calls
        self.cache = {}
        self.cache_ttl = 5  # seconds
        
        logger.info("✅ Market Data initialized (Native SDK)")
    
    async def get_market_snapshot(self, market_id: int) -> Dict[str, Any]:
        """
        Get current market snapshot (ticker data)
        Uses native order_book_details for efficient retrieval
        
        Args:
            market_id: Market ID (e.g., 0 for ETH-USD)
            
        Returns:
            Market snapshot with price, volume, spread
        """
        try:
            # Check cache
            cache_key = f"snapshot_{market_id}"
            if cache_key in self.cache:
                cached_time, cached_data = self.cache[cache_key]
                if time.time() - cached_time < self.cache_ttl:
                    return cached_data
            
            # Get order book details (includes ticker info)
            response = await self.order_api.order_book_details(market_id=market_id)
            
            if not response or not response.data:
                logger.warning(f"No market data for market {market_id}")
                return {}
            
            details = response.data[0] if isinstance(response.data, list) else response.data
            
            snapshot = {
                'market_id': market_id,
                'last_price': float(details.last_price) if hasattr(details, 'last_price') else 0,
                'best_bid': float(details.best_bid) if hasattr(details, 'best_bid') else 0,
                'best_ask': float(details.best_ask) if hasattr(details, 'best_ask') else 0,
                'spread': float(details.spread) if hasattr(details, 'spread') else 0,
                'volume_24h': float(details.volume_24h) if hasattr(details, 'volume_24h') else 0,
                'price_change_24h': float(details.price_change_24h) if hasattr(details, 'price_change_24h') else 0,
                'high_24h': float(details.high_24h) if hasattr(details, 'high_24h') else 0,
                'low_24h': float(details.low_24h) if hasattr(details, 'low_24h') else 0,
                'timestamp': int(time.time() * 1000)
            }
            
            # Cache result
            self.cache[cache_key] = (time.time(), snapshot)
            
            return snapshot
            
        except Exception as e:
            logger.error(f"❌ Failed to get market snapshot: {e}")
            return {}
    
    async def get_order_book(self, market_id: int, limit: int = 20) -> Dict[str, Any]:
        """
        Get full order book with bids and asks
        
        Args:
            market_id: Market ID
            limit: Number of price levels per side
            
        Returns:
            Order book with bids and asks
        """
        try:
            response = await self.order_api.order_books(market_id=market_id)
            
            if not response or not response.data:
                return {'bids': [], 'asks': []}
            
            book = response.data[0] if isinstance(response.data, list) else response.data
            
            # Extract bids and asks
            bids = []
            asks = []
            
            if hasattr(book, 'bids') and book.bids:
                for bid in book.bids[:limit]:
                    bids.append({
                        'price': float(bid.price) if hasattr(bid, 'price') else 0,
                        'size': float(bid.size) if hasattr(bid, 'size') else 0
                    })
            
            if hasattr(book, 'asks') and book.asks:
                for ask in book.asks[:limit]:
                    asks.append({
                        'price': float(ask.price) if hasattr(ask, 'price') else 0,
                        'size': float(ask.size) if hasattr(ask, 'size') else 0
                    })
            
            return {
                'market_id': market_id,
                'bids': bids,
                'asks': asks,
                'timestamp': int(time.time() * 1000)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get order book: {e}")
            return {'bids': [], 'asks': []}
    
    async def get_candlesticks(self, market_id: int, resolution: str,
                               count_back: int = 100) -> List[Dict[str, Any]]:
        """
        Get historical candlestick data using native SDK
        
        Args:
            market_id: Market ID
            resolution: Candle resolution ('1m', '5m', '15m', '1h', '4h', '1d')
            count_back: Number of candles to retrieve
            
        Returns:
            List of OHLCV candles
        """
        try:
            # Calculate time range
            end_time = int(time.time() * 1000)
            resolution_ms = self._resolution_to_ms(resolution)
            start_time = end_time - (count_back * resolution_ms)
            
            # Use native SDK method
            response = await self.candle_api.candlesticks(
                market_id=market_id,
                resolution=resolution,
                start_timestamp=start_time,
                end_timestamp=end_time,
                count_back=count_back
            )
            
            if not response or not response.data:
                return []
            
            # Convert to standard format
            candles = []
            for candle in response.data:
                candles.append({
                    'timestamp': candle.timestamp if hasattr(candle, 'timestamp') else 0,
                    'open': float(candle.open) if hasattr(candle, 'open') else 0,
                    'high': float(candle.high) if hasattr(candle, 'high') else 0,
                    'low': float(candle.low) if hasattr(candle, 'low') else 0,
                    'close': float(candle.close) if hasattr(candle, 'close') else 0,
                    'volume': float(candle.volume) if hasattr(candle, 'volume') else 0
                })
            
            logger.debug(f"✅ Retrieved {len(candles)} candles ({resolution})")
            return candles
            
        except Exception as e:
            logger.error(f"❌ Failed to get candlesticks: {e}")
            return []
    
    async def get_recent_trades(self, market_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent market trades
        
        Args:
            market_id: Market ID
            limit: Number of trades to retrieve
            
        Returns:
            List of recent trades
        """
        try:
            response = await self.order_api.recent_trades(
                market_id=market_id,
                limit=limit
            )
            
            if not response or not response.data:
                return []
            
            trades = []
            for trade in response.data:
                trades.append({
                    'id': trade.id if hasattr(trade, 'id') else None,
                    'price': float(trade.price) if hasattr(trade, 'price') else 0,
                    'size': float(trade.size) if hasattr(trade, 'size') else 0,
                    'side': 'buy' if not trade.is_ask else 'sell',
                    'timestamp': trade.timestamp if hasattr(trade, 'timestamp') else 0
                })
            
            return trades
            
        except Exception as e:
            logger.error(f"❌ Failed to get recent trades: {e}")
            return []
    
    async def get_funding_rate(self, market_id: int = None) -> Dict[str, Any]:
        """
        Get current funding rate
        
        Args:
            market_id: Optional market ID (None for all markets)
            
        Returns:
            Funding rate data
        """
        try:
            response = await self.funding_api.funding_rates()
            
            if not response or not response.data:
                return {}
            
            # If specific market requested
            if market_id is not None:
                for rate in response.data:
                    if hasattr(rate, 'market_id') and rate.market_id == market_id:
                        return {
                            'market_id': rate.market_id,
                            'funding_rate': float(rate.funding_rate) if hasattr(rate, 'funding_rate') else 0,
                            'next_funding_time': rate.next_funding_time if hasattr(rate, 'next_funding_time') else None
                        }
                return {}
            
            # Return all rates
            rates = {}
            for rate in response.data:
                if hasattr(rate, 'market_id'):
                    rates[rate.market_id] = {
                        'funding_rate': float(rate.funding_rate) if hasattr(rate, 'funding_rate') else 0,
                        'next_funding_time': rate.next_funding_time if hasattr(rate, 'next_funding_time') else None
                    }
            
            return rates
            
        except Exception as e:
            logger.error(f"❌ Failed to get funding rate: {e}")
            return {}
    
    async def get_exchange_stats(self) -> Dict[str, Any]:
        """
        Get global exchange statistics
        
        Returns:
            Exchange stats including volume, users, trades
        """
        try:
            response = await self.order_api.exchange_stats()
            
            if not response or not response.data:
                return {}
            
            stats = response.data
            
            return {
                'total_volume_24h': float(stats.total_volume_24h) if hasattr(stats, 'total_volume_24h') else 0,
                'total_trades_24h': int(stats.total_trades_24h) if hasattr(stats, 'total_trades_24h') else 0,
                'active_users_24h': int(stats.active_users_24h) if hasattr(stats, 'active_users_24h') else 0,
                'open_interest': float(stats.open_interest) if hasattr(stats, 'open_interest') else 0
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get exchange stats: {e}")
            return {}
    
    def _resolution_to_ms(self, resolution: str) -> int:
        """Convert resolution string to milliseconds"""
        resolution_map = {
            '1m': 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000,
            '1w': 7 * 24 * 60 * 60 * 1000
        }
        return resolution_map.get(resolution, 60 * 1000)  # Default 1m
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        logger.info("🗑️  Market data cache cleared")


# Convenience function
async def get_current_price(api_client, market_id: int = 0) -> float:
    """
    Quick function to get current market price
    
    Args:
        api_client: ApiClient instance
        market_id: Market ID
        
    Returns:
        Current price
    """
    market_data = MarketDataV2(api_client)
    snapshot = await market_data.get_market_snapshot(market_id)
    return snapshot.get('last_price', 0)
