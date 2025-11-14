"""
Rate Limiting Protection System
Prevents API 429 errors with intelligent request throttling
"""
import asyncio
import time
from collections import deque
from typing import Optional, Callable, Any
from datetime import datetime, timedelta
from logger import logger


class RateLimiter:
    """
    Advanced rate limiter with:
    - Token bucket algorithm
    - Exponential backoff on 429 errors
    - Request batching
    - Automatic cooldown
    """
    
    def __init__(
        self,
        requests_per_second: float = 0.5,  # Ultra-conservative: 1 request every 2 seconds
        burst_size: int = 2,  # Allow burst of 2 requests
        backoff_base: float = 3.0,  # Exponential backoff multiplier
        max_backoff: float = 120.0,  # Max 2 minute backoff
    ):
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        self.backoff_base = backoff_base
        self.max_backoff = max_backoff
        
        # Token bucket
        self.tokens = burst_size
        self.last_refill = time.time()
        
        # Backoff state
        self.consecutive_429s = 0
        self.backoff_until = None
        
        # Request tracking
        self.request_times = deque(maxlen=100)  # Last 100 requests
        self.total_requests = 0
        self.total_429_errors = 0
        
        logger.info(f"🚦 Rate Limiter initialized: {requests_per_second} req/s, burst={burst_size}")
    
    def _refill_tokens(self):
        """Refill tokens based on time elapsed"""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.requests_per_second
        self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
        self.last_refill = now
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens to make a request
        
        Args:
            tokens: Number of tokens to acquire (default 1)
            
        Returns:
            True if acquired, False if in backoff period
        """
        # Check if we're in backoff period
        if self.backoff_until:
            if datetime.now() < self.backoff_until:
                remaining = (self.backoff_until - datetime.now()).total_seconds()
                logger.debug(f"⏳ In backoff period, {remaining:.1f}s remaining")
                return False
            else:
                # Backoff period ended
                logger.info(f"✅ Backoff period ended, resuming requests")
                self.backoff_until = None
                self.consecutive_429s = 0
        
        # Refill tokens
        self._refill_tokens()
        
        # Check if we have enough tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            self.request_times.append(time.time())
            self.total_requests += 1
            return True
        else:
            # Not enough tokens, wait
            wait_time = (tokens - self.tokens) / self.requests_per_second
            logger.debug(f"⏱️ Rate limit: waiting {wait_time:.2f}s for tokens")
            await asyncio.sleep(wait_time)
            
            # Try again after waiting
            self._refill_tokens()
            if self.tokens >= tokens:
                self.tokens -= tokens
                self.request_times.append(time.time())
                self.total_requests += 1
                return True
            
            return False
    
    def report_429_error(self):
        """Report a 429 error and trigger exponential backoff"""
        self.total_429_errors += 1
        self.consecutive_429s += 1
        
        # Calculate backoff time with exponential increase
        backoff_seconds = min(
            self.backoff_base ** self.consecutive_429s,
            self.max_backoff
        )
        
        self.backoff_until = datetime.now() + timedelta(seconds=backoff_seconds)
        
        logger.warning(
            f"🚨 429 Error #{self.consecutive_429s}: "
            f"Backing off for {backoff_seconds:.1f}s until {self.backoff_until.strftime('%H:%M:%S')}"
        )
    
    def report_success(self):
        """Report a successful request (resets consecutive 429 count)"""
        if self.consecutive_429s > 0:
            logger.info(f"✅ Request successful after {self.consecutive_429s} 429 errors, resetting backoff")
        self.consecutive_429s = 0
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        max_retries: int = 3,
        **kwargs
    ) -> Optional[Any]:
        """
        Execute a function with automatic retry on 429 errors
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            max_retries: Maximum number of retries
            **kwargs: Keyword arguments for func
            
        Returns:
            Function result or None if all retries failed
        """
        for attempt in range(max_retries):
            try:
                # Wait for rate limit clearance
                acquired = await self.acquire()
                if not acquired:
                    logger.warning(f"⏸️ Rate limit not acquired on attempt {attempt + 1}/{max_retries}")
                    await asyncio.sleep(1)
                    continue
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Success!
                self.report_success()
                return result
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a 429 error
                if "429" in error_str or "Too Many Requests" in error_str:
                    self.report_429_error()
                    
                    if attempt < max_retries - 1:
                        # Wait for backoff period
                        if self.backoff_until:
                            wait_time = (self.backoff_until - datetime.now()).total_seconds()
                            if wait_time > 0:
                                logger.info(f"⏳ Waiting {wait_time:.1f}s before retry {attempt + 2}/{max_retries}")
                                await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"❌ Max retries ({max_retries}) exceeded for rate-limited request")
                        return None
                else:
                    # Non-429 error, don't retry
                    logger.error(f"❌ Error in rate-limited request: {e}")
                    raise
        
        return None
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        return {
            'total_requests': self.total_requests,
            'total_429_errors': self.total_429_errors,
            'consecutive_429s': self.consecutive_429s,
            'tokens_available': self.tokens,
            'in_backoff': self.backoff_until is not None,
            'backoff_until': self.backoff_until.isoformat() if self.backoff_until else None,
            '429_rate': f"{(self.total_429_errors / max(self.total_requests, 1) * 100):.2f}%"
        }


# Global rate limiter instance
global_rate_limiter = RateLimiter(
    requests_per_second=2.0,  # Conservative: 2 requests per second
    burst_size=5,
    backoff_base=2.0,
    max_backoff=60.0
)


async def rate_limited_call(func: Callable, *args, **kwargs) -> Optional[Any]:
    """
    Convenience function to make a rate-limited API call
    
    Usage:
        result = await rate_limited_call(client.get_orderbook, market_id=0)
    """
    return await global_rate_limiter.execute_with_retry(func, *args, **kwargs)
