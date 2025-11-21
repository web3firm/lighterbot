"""
Error Handler - Centralized error handling and recovery
"""

import logging
import traceback
from typing import Optional, Callable, Any
from datetime import datetime, timezone
from functools import wraps

logger = logging.getLogger(__name__)


class ErrorHandler:
    """
    Centralized error handling with logging and recovery
    """
    
    def __init__(self):
        """Initialize error handler"""
        self.error_count = 0
        self.last_error_time: Optional[datetime] = None
        self.error_history = []
        
        logger.info("✅ Error handler initialized")
    
    def handle_error(self, error: Exception, context: str = "", fatal: bool = False):
        """
        Handle error with logging and optional recovery
        
        Args:
            error: Exception that occurred
            context: Context description
            fatal: Whether error is fatal (should stop bot)
        """
        self.error_count += 1
        self.last_error_time = datetime.now(timezone.utc)
        
        error_info = {
            'timestamp': self.last_error_time.isoformat(),
            'context': context,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'fatal': fatal,
            'traceback': traceback.format_exc()
        }
        
        self.error_history.append(error_info)
        
        # Log error
        if fatal:
            logger.critical(f"🚨 FATAL ERROR in {context}")
        else:
            logger.error(f"❌ ERROR in {context}")
        
        logger.error(f"   Type: {type(error).__name__}")
        logger.error(f"   Message: {str(error)}")
        
        if fatal:
            logger.critical(f"   Traceback:\n{traceback.format_exc()}")
        
        return error_info
    
    def get_error_stats(self) -> dict:
        """Get error statistics"""
        return {
            'total_errors': self.error_count,
            'last_error_time': self.last_error_time.isoformat() if self.last_error_time else None,
            'recent_errors': self.error_history[-10:]  # Last 10 errors
        }


def error_handler_decorator(context: str = "", fatal: bool = False, default_return: Any = None):
    """
    Decorator for error handling
    
    Args:
        context: Context description
        fatal: Whether error is fatal
        default_return: Default return value on error
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                handler = ErrorHandler()
                handler.handle_error(e, context or func.__name__, fatal)
                return default_return
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handler = ErrorHandler()
                handler.handle_error(e, context or func.__name__, fatal)
                return default_return
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Global error handler instance
_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get or create global error handler"""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


if __name__ == "__main__":
    import asyncio
    
    # Test error handler
    handler = get_error_handler()
    
    try:
        raise ValueError("Test error")
    except Exception as e:
        handler.handle_error(e, "test_context")
    
    stats = handler.get_error_stats()
    print(f"Error stats: {stats}")
