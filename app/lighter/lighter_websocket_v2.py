"""
Lighter WebSocket V2 - Native SDK Implementation
Replaces 200+ lines of custom WebSocket code with ~60 lines using SDK's WsClient
Real-time order and account updates instead of polling
"""

import logging
import lighter
from typing import Callable, Optional, Dict, Any
import asyncio

logger = logging.getLogger(__name__)


class LighterWebSocketV2:
    """
    Native SDK-based WebSocket client
    Provides real-time updates for account and order book data
    """
    
    def __init__(self, api_url: str, account_index: int):
        """
        Initialize WebSocket client using native SDK
        
        Args:
            api_url: API URL (e.g., 'https://api.lighter.xyz/v1')
            account_index: Account index for subscriptions
        """
        # Convert HTTP URL to WebSocket URL
        ws_url = api_url.replace('https://', 'wss://').replace('http://', 'ws://').replace('/v1', '/ws')
        
        self.ws_url = ws_url
        self.account_index = account_index
        self.ws_client = None
        
        # Callbacks
        self.account_callback: Optional[Callable] = None
        self.orderbook_callback: Optional[Callable] = None
        self.connected_callback: Optional[Callable] = None
        self.error_callback: Optional[Callable] = None
        
        logger.info(f"🔌 WebSocket V2 initialized (Native SDK)")
        logger.info(f"   URL: {ws_url}")
        logger.info(f"   Account: {account_index}")
    
    async def connect(self) -> bool:
        """
        Connect to WebSocket using native SDK client
        
        Returns:
            True if connected successfully
        """
        try:
            logger.info("🔌 Connecting to WebSocket...")
            
            # Create native WsClient
            self.ws_client = lighter.WsClient(
                api_url=self.ws_url,
                account_index=self.account_index
            )
            
            # Set up handlers
            self._setup_handlers()
            
            # Connect (SDK handles connection internally)
            await self.ws_client.connect()
            
            logger.info("✅ WebSocket connected (Native SDK)")
            
            if self.connected_callback:
                await self.connected_callback()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            if self.error_callback:
                await self.error_callback(e)
            return False
    
    def _setup_handlers(self):
        """Set up native SDK event handlers"""
        
        # Connected handler
        original_connected = self.ws_client.handle_connected_async
        async def on_connected():
            logger.info("✅ WebSocket connected event")
            if self.connected_callback:
                await self.connected_callback()
            if original_connected:
                await original_connected()
        
        self.ws_client.handle_connected_async = on_connected
        
        # Account update handler
        original_account = self.ws_client.handle_update_account
        def on_account_update(update):
            try:
                logger.debug(f"📊 Account update received")
                if self.account_callback:
                    asyncio.create_task(self._safe_callback(self.account_callback, update))
                if original_account:
                    original_account(update)
            except Exception as e:
                logger.error(f"Error in account update handler: {e}")
        
        self.ws_client.handle_update_account = on_account_update
        
        # Order book update handler
        original_orderbook = self.ws_client.handle_update_order_book
        def on_orderbook_update(update):
            try:
                logger.debug(f"📖 Order book update received")
                if self.orderbook_callback:
                    asyncio.create_task(self._safe_callback(self.orderbook_callback, update))
                if original_orderbook:
                    original_orderbook(update)
            except Exception as e:
                logger.error(f"Error in order book update handler: {e}")
        
        self.ws_client.handle_update_order_book = on_orderbook_update
        
        # Error handler
        original_error = self.ws_client.on_error
        def on_error(ws, error):
            logger.error(f"❌ WebSocket error: {error}")
            if self.error_callback:
                asyncio.create_task(self._safe_callback(self.error_callback, error))
            if original_error:
                original_error(ws, error)
        
        self.ws_client.on_error = on_error
        
        # Close handler
        original_close = self.ws_client.on_close
        def on_close(ws, close_status_code, close_msg):
            logger.warning(f"⚠️  WebSocket closed: {close_status_code} - {close_msg}")
            if original_close:
                original_close(ws, close_status_code, close_msg)
        
        self.ws_client.on_close = on_close
    
    async def _safe_callback(self, callback: Callable, data: Any):
        """Safely execute callback with error handling"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
        except Exception as e:
            logger.error(f"Error in callback: {e}")
            logger.exception(e)
    
    async def subscribe_account(self, callback: Callable) -> bool:
        """
        Subscribe to account updates (balance, orders, positions)
        
        Args:
            callback: Async function to call on updates
            
        Returns:
            True if subscribed
        """
        try:
            if not self.ws_client:
                logger.error("❌ WebSocket not connected")
                return False
            
            self.account_callback = callback
            await self.ws_client.subscribe_account()
            
            logger.info(f"✅ Subscribed to account updates (Account: {self.account_index})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe to account: {e}")
            return False
    
    async def subscribe_orderbook(self, market_id: int, callback: Callable) -> bool:
        """
        Subscribe to order book updates for a market
        
        Args:
            market_id: Market ID (e.g., 0 for ETH-USD)
            callback: Async function to call on updates
            
        Returns:
            True if subscribed
        """
        try:
            if not self.ws_client:
                logger.error("❌ WebSocket not connected")
                return False
            
            self.orderbook_callback = callback
            await self.ws_client.subscribe_order_book(market_id)
            
            logger.info(f"✅ Subscribed to order book updates (Market: {market_id})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe to order book: {e}")
            return False
    
    def on_connected(self, callback: Callable):
        """Set callback for connection events"""
        self.connected_callback = callback
    
    def on_error(self, callback: Callable):
        """Set callback for error events"""
        self.error_callback = callback
    
    async def close(self):
        """Close WebSocket connection"""
        try:
            if self.ws_client:
                await self.ws_client.close()
                logger.info("✅ WebSocket closed")
        except Exception as e:
            logger.error(f"❌ Error closing WebSocket: {e}")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self.ws_client is not None


# Example usage helper
async def create_realtime_monitor(api_url: str, account_index: int,
                                 on_account_update: Callable,
                                 on_orderbook_update: Optional[Callable] = None,
                                 market_id: Optional[int] = None) -> LighterWebSocketV2:
    """
    Quick setup for real-time monitoring
    
    Args:
        api_url: API URL
        account_index: Account index
        on_account_update: Callback for account updates
        on_orderbook_update: Optional callback for order book updates
        market_id: Optional market ID for order book subscription
        
    Returns:
        Connected WebSocket client
    """
    ws = LighterWebSocketV2(api_url, account_index)
    
    # Connect
    connected = await ws.connect()
    if not connected:
        raise Exception("Failed to connect WebSocket")
    
    # Subscribe to account updates
    await ws.subscribe_account(on_account_update)
    
    # Subscribe to order book if requested
    if on_orderbook_update and market_id is not None:
        await ws.subscribe_orderbook(market_id, on_orderbook_update)
    
    return ws
