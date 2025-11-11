"""Utility and resilience components for the Lighter trading bot.

This module provides:
  * MarketMetadata: dynamic decimal precision + conversion helpers
  * OrderIndexer: persistent client order index counter across restarts
  * retry_async: exponential backoff retry decorator for async functions
  * CircuitBreaker + circuit_breaker decorator: protect unstable external calls
  * resolve_market_metadata: register known markets and set precision
  * Formatting helpers for size, price, and PnL

Exports used elsewhere:
    market_metadata, order_indexer, retry_async,
    CircuitBreaker, circuit_breaker, lighter_api_breaker,
    resolve_market_metadata
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from config import settings
from logger import logger

T = TypeVar("T")


class MarketMetadata:
    """Thread-safe market metadata storage.

    Stores comprehensive market data from official Lighter API including:
        base_decimals: decimals for base asset sizing (lots multiplier)
        quote_decimals: decimals for quote asset (USDC = 6)
        price_decimals: decimals for price integer conversion
        min_base_amount: minimum order size in base units
        min_quote_amount: minimum order value in quote units
        maker_fee: maker fee percentage
        taker_fee: taker fee percentage  
        liquidation_fee: liquidation fee percentage
        status: market status (active/inactive)
    """

    def __init__(self) -> None:
        self._markets: Dict[int, Dict[str, Any]] = {}
        self._symbol_to_id: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def set_market(
        self,
        market_id: int,
        symbol: str,
        base_decimals: int,
        quote_decimals: int,
        price_decimals: int,
        min_base_amount: Optional[float] = None,
        min_quote_amount: Optional[float] = None,
        maker_fee: Optional[float] = None,
        taker_fee: Optional[float] = None,
        liquidation_fee: Optional[float] = None,
        status: Optional[str] = None,
    ) -> None:
        async with self._lock:
            self._markets[market_id] = {
                "base_decimals": base_decimals,
                "quote_decimals": quote_decimals,
                "price_decimals": price_decimals,
                "symbol": symbol,
                "min_base_amount": min_base_amount,
                "min_quote_amount": min_quote_amount,
                "maker_fee": maker_fee,
                "taker_fee": taker_fee,
                "liquidation_fee": liquidation_fee,
                "status": status,
            }
            self._symbol_to_id[symbol] = market_id
            logger.debug(
                f"Registered market {symbol} id={market_id} base={base_decimals} price={price_decimals}"
            )
            if min_base_amount:
                logger.debug(f"  Min amounts: base={min_base_amount}, quote={min_quote_amount}")
            if maker_fee is not None:
                logger.debug(f"  Fees: maker={maker_fee}%, taker={taker_fee}%, liquidation={liquidation_fee}%")
            if status:
                logger.debug(f"  Status: {status}")

    def get_market(self, market_id: int) -> Dict[str, Any]:
        return self._markets.get(market_id, {})

    def get_market_id(self, symbol: str) -> Optional[int]:
        return self._symbol_to_id.get(symbol)
    
    def get_min_order_size(self, market_id: int) -> float:
        """Get minimum order size from API data, fallback to 0.001"""
        market = self._markets.get(market_id, {})
        return market.get("min_base_amount", 0.001)
    
    def get_fees(self, market_id: int) -> Dict[str, float]:
        """Get fee structure for market"""
        market = self._markets.get(market_id, {})
        return {
            "maker": market.get("maker_fee", 0.0),
            "taker": market.get("taker_fee", 0.0),
            "liquidation": market.get("liquidation_fee", 1.0)
        }
    
    def is_market_active(self, market_id: int) -> bool:
        """Check if market is active for trading"""
        market = self._markets.get(market_id, {})
        status = market.get("status", "unknown")
        return status and status.lower() == "active"

    def to_base_amount(self, size: float, market_id: int) -> int:
        info = self.get_market(market_id)
        base_decimals = info.get("base_decimals", 6)
        return int(round(size * (10 ** base_decimals)))

    def from_base_amount(self, base_amount: int, market_id: int) -> float:
        info = self.get_market(market_id)
        base_decimals = info.get("base_decimals", 6)
        return base_amount / (10 ** base_decimals)

    def to_price_int(self, price: float, market_id: int) -> int:
        info = self.get_market(market_id)
        price_decimals = info.get("price_decimals", 2)
        return int(round(price * (10 ** price_decimals)))

    def from_price_int(self, price_int: int, market_id: int) -> float:
        info = self.get_market(market_id)
        price_decimals = info.get("price_decimals", 2)
        return price_int / (10 ** price_decimals)


market_metadata = MarketMetadata()


class OrderIndexer:
    """Persistent client order index counter.

    Stores last index in a JSON file so we don't collide after restarts.
    """

    def __init__(self, file_path: str = "data/order_index.json") -> None:
        self.file_path = file_path
        self._lock = asyncio.Lock()
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            self._write_state({"last_index": 0})

    def _read_state(self) -> Dict[str, int]:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except Exception:
            return {"last_index": 0}

    def _write_state(self, data: Dict[str, int]) -> None:
        tmp_path = self.file_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f)
        os.replace(tmp_path, self.file_path)

    async def get_next(self) -> int:
        async with self._lock:
            state = self._read_state()
            nxt = state.get("last_index", 0) + 1
            state["last_index"] = nxt
            self._write_state(state)
            return nxt

    async def peek(self) -> int:
        async with self._lock:
            state = self._read_state()
            return state.get("last_index", 0)


order_indexer = OrderIndexer()


def retry_async(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[type, ...] = (Exception,),
):
    """Async exponential backoff retry decorator."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            attempt = 0
            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts", exc_info=True
                        )
                        raise
                    delay = min(initial_delay * (exponential_base ** (attempt - 1)), max_delay)
                    if jitter:
                        delay *= 0.5 + random.random()
                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}; retrying in {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
            raise RuntimeError(f"Retry logic error in {func.__name__}")

        return wrapper  # type: ignore

    return decorator


async def resolve_market_metadata(client: Any, symbol: str = None, market_id: int = None) -> Optional[int]:
    """
    Fetch and register market metadata from Lighter API.
    
    Args:
        client: Lighter client instance
        symbol: Market symbol (e.g., "BTC-PERP", "ETH", "BTC")
        market_id: Market ID to query directly
        
    Returns:
        Market ID if successful, None otherwise
    """
    try:
        logger.info(f"Fetching market metadata from Lighter API...")
        
        # Get all markets from official API
        import lighter
        config = lighter.Configuration(host=settings.lighter_base_url)
        async with lighter.ApiClient(configuration=config) as api_client:
            order_api = lighter.OrderApi(api_client)
            result = await order_api.order_books()
            
            if not hasattr(result, 'order_books'):
                logger.error("Failed to fetch order books from API")
                return None
            
            # Find the market by ID or symbol
            target_market = None
            
            # Clean symbol for matching (remove -PERP suffix if present)
            clean_symbol = symbol.replace('-PERP', '').upper() if symbol else None
            
            for market in result.order_books:
                # Match by market ID first (most reliable)
                if market_id and market.market_id == market_id:
                    target_market = market
                    logger.info(f"Found market by ID: {market.symbol} (ID: {market.market_id})")
                    break
                    
                # Match by symbol (clean both for comparison)
                if clean_symbol and market.symbol.upper() == clean_symbol:
                    target_market = market
                    logger.info(f"Found market by symbol: {market.symbol} (ID: {market.market_id})")
                    break
            
            if not target_market:
                logger.error(f"Market not found - Symbol: {symbol}, ID: {market_id}")
                logger.info(f"Available markets: {', '.join([m.symbol for m in result.order_books[:10]])}...")
                return None
            
            # Extract metadata from API response
            detected_symbol = target_market.symbol
            detected_market_id = target_market.market_id
            
            # API provides complete market metadata:
            # - supported_size_decimals: base asset decimals
            # - supported_price_decimals: price decimals
            # - supported_quote_decimals: quote asset (USDC) decimals
            # - min_base_amount: minimum order size in base units
            # - min_quote_amount: minimum order value in quote units
            # - maker_fee, taker_fee, liquidation_fee: fee percentages
            # - status: market status (active/inactive)
            base_decimals = target_market.supported_size_decimals
            price_decimals = target_market.supported_price_decimals
            quote_decimals = target_market.supported_quote_decimals
            min_base = float(target_market.min_base_amount) if hasattr(target_market, 'min_base_amount') else None
            min_quote = float(target_market.min_quote_amount) if hasattr(target_market, 'min_quote_amount') else None
            maker_fee = float(target_market.maker_fee) if hasattr(target_market, 'maker_fee') else None
            taker_fee = float(target_market.taker_fee) if hasattr(target_market, 'taker_fee') else None
            liquidation_fee = float(target_market.liquidation_fee) if hasattr(target_market, 'liquidation_fee') else None
            market_status = target_market.status if hasattr(target_market, 'status') else None
            
            # Register in our metadata cache with COMPLETE data
            await market_metadata.set_market(
                market_id=detected_market_id,
                symbol=f"{detected_symbol}-PERP",  # Add -PERP suffix for consistency
                base_decimals=base_decimals,
                quote_decimals=quote_decimals,
                price_decimals=price_decimals,
                min_base_amount=min_base,
                min_quote_amount=min_quote,
                maker_fee=maker_fee,
                taker_fee=taker_fee,
                liquidation_fee=liquidation_fee,
                status=market_status,
            )
            
            logger.info(
                f"✓ Registered {detected_symbol}-PERP (Market ID: {detected_market_id}) from API"
            )
            logger.info(
                f"  Base decimals: {base_decimals}, Price decimals: {price_decimals}, "
                f"Quote decimals: {quote_decimals}"
            )
            
            if min_base:
                logger.info(
                    f"  Min base amount: {min_base}, "
                    f"Min quote amount: {min_quote}"
                )
            
            if maker_fee is not None:
                logger.info(
                    f"  Fees - Maker: {maker_fee}%, Taker: {taker_fee}%, "
                    f"Liquidation: {liquidation_fee}%"
                )
            
            if market_status:
                status_emoji = "✅" if market_status.lower() == "active" else "⚠️"
                logger.info(f"  {status_emoji} Market Status: {market_status}")
            
            return detected_market_id
            
    except Exception as e:
        logger.error(f"Error fetching market metadata from API: {e}", exc_info=True)
        logger.warning("Will not use fallback hardcoded values - API should be the source of truth")
        return None


def format_size(size: float, decimals: int = 4) -> str:
    return f"{size:.{decimals}f}".rstrip("0").rstrip(".")


def format_price(price: float, decimals: int = 2) -> str:
    return f"${price:,.{decimals}f}"


def format_pnl(pnl: float) -> str:
    sign = "+" if pnl >= 0 else ""
    return f"{sign}${pnl:,.2f}"


class CircuitBreaker:
    """Simple async-aware circuit breaker."""

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls
        self._state: str = "closed"  # closed | open | half_open
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._half_open_in_flight: int = 0
        self._lock = asyncio.Lock()

    async def allow_call(self) -> bool:
        async with self._lock:
            now = time.time()
            if self._state == "open":
                if now - self._last_failure_time >= self.reset_timeout:
                    self._state = "half_open"
                    self._half_open_in_flight = 0
                else:
                    return False
            if self._state == "half_open":
                if self._half_open_in_flight >= self.half_open_max_calls:
                    return False
                self._half_open_in_flight += 1
                return True
            return True

    async def on_success(self) -> None:
        async with self._lock:
            if self._state in ("half_open", "open"):
                self._state = "closed"
                self._failure_count = 0
                self._half_open_in_flight = 0
                self._last_failure_time = 0.0

    async def on_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._state == "half_open" or self._failure_count >= self.failure_threshold:
                self._state = "open"
                self._half_open_in_flight = 0

    # Introspection helpers
    def state(self) -> str:
        return self._state

    def failure_count(self) -> int:
        return self._failure_count


def circuit_breaker(
    breaker: CircuitBreaker,
    exceptions: Tuple[type, ...] = (Exception,),
):
    """Decorator to enforce circuit breaker around async call."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs):
            allowed = await breaker.allow_call()
            if not allowed:
                raise RuntimeError("Circuit breaker is open; rejecting call")
            try:
                result = await func(*args, **kwargs)
                await breaker.on_success()
                return result
            except exceptions:
                await breaker.on_failure()
                raise

        return wrapper  # type: ignore

    return decorator


# Global circuit breaker instance configured from settings
lighter_api_breaker = CircuitBreaker(
    failure_threshold=settings.cb_failure_threshold,
    reset_timeout=settings.cb_reset_timeout,
    half_open_max_calls=settings.cb_half_open_max_calls,
)


__all__ = [
    "market_metadata",
    "order_indexer",
    "retry_async",
    "resolve_market_metadata",
    "CircuitBreaker",
    "circuit_breaker",
    "lighter_api_breaker",
    "OrderIndexer",
    "MarketMetadata",
    "format_size",
    "format_price",
    "format_pnl",
]

