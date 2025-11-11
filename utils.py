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
    """Holds market decimal metadata and provides conversion helpers.

    Stored per market_id:
        base_decimals: decimals for base asset sizing (lots multiplier)
        quote_decimals: decimals for quote asset (not heavily used yet)
        price_decimals: decimals for price integer conversion
    """

    def __init__(self) -> None:
        self._markets: Dict[int, Dict[str, int]] = {}
        self._symbol_to_id: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def set_market(
        self,
        market_id: int,
        symbol: str,
        base_decimals: int,
        quote_decimals: int,
        price_decimals: int,
    ) -> None:
        async with self._lock:
            self._markets[market_id] = {
                "base_decimals": base_decimals,
                "quote_decimals": quote_decimals,
                "price_decimals": price_decimals,
                "symbol": symbol,
            }
            self._symbol_to_id[symbol] = market_id
            logger.debug(
                f"Registered market {symbol} id={market_id} base={base_decimals} price={price_decimals}"
            )

    def get_market(self, market_id: int) -> Dict[str, Any]:
        return self._markets.get(market_id, {})

    def get_market_id(self, symbol: str) -> Optional[int]:
        return self._symbol_to_id.get(symbol)

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


async def resolve_market_metadata(client: Any, symbol: str) -> Optional[int]:
    """Register known market metadata for a symbol. Returns market_id or None."""
    try:
        logger.info(f"Resolving market metadata for {symbol}...")
        known_markets = {
            "BTC-PERP": {"id": 1, "base_decimals": 6, "price_decimals": 2},
            "ETH-PERP": {"id": 2, "base_decimals": 6, "price_decimals": 2},
            "NEAR-PERP": {"id": 3, "base_decimals": 6, "price_decimals": 2},
        }
        if symbol in known_markets:
            info = known_markets[symbol]
            await market_metadata.set_market(
                market_id=info["id"],
                symbol=symbol,
                base_decimals=info["base_decimals"],
                quote_decimals=6,
                price_decimals=info["price_decimals"],
            )
            logger.info(
                f"Registered {symbol} id={info['id']} base={info['base_decimals']} price={info['price_decimals']}"
            )
            return info["id"]
        logger.error(f"Unknown market symbol: {symbol}")
        return None
    except Exception as e:
        logger.error(f"Error resolving market metadata: {e}", exc_info=True)
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

