"""
Lighter Protocol Client - SDK Wrapper
Interfaces with Lighter Protocol on Arbitrum via lighter-python SDK
"""

import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal
import asyncio
import lighter

logger = logging.getLogger(__name__)


class LighterClient:
    """
    Wrapper for lighter-python SDK
    Provides simplified interface for Lighter Protocol trading
    """
    
    def __init__(self, api_url: str, api_private_key: str, api_key_index: int, account_index: int):
        """
        Initialize Lighter Protocol client
        
        Args:
            api_url: Lighter API endpoint
            api_private_key: API private key
            api_key_index: API key index
            account_index: Account index
        """
        self.api_url = api_url
        self.api_private_key = api_private_key
        self.api_key_index = api_key_index
        self.account_index = account_index
        
        # Initialize lighter SDK clients
        self.api_client = None
        self.signer_client = None
        self.account_api = None
        self.order_api = None
        self.transaction_api = None
        self.candlestick_api = None
        
        self.connected = False
        
        logger.info(f"✅ Lighter client initialized")
        logger.info(f"   API URL: {api_url}")
        logger.info(f"   Account Index: {account_index}")
        logger.info(f"   API Key Index: {api_key_index}")
    
    
    async def connect(self) -> bool:
        """
        Establish connection to Lighter Protocol
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Initialize API client
            config = lighter.Configuration(host=self.api_url)
            self.api_client = lighter.ApiClient(configuration=config)
            
            # Initialize SignerClient for trading operations
            self.signer_client = lighter.SignerClient(
                url=self.api_url,
                private_key=self.api_private_key,
                api_key_index=self.api_key_index,
                account_index=self.account_index
            )
            
            # Verify API key is valid
            err = self.signer_client.check_client()
            if err is not None:
                logger.error(f"❌ API key verification failed: {err}")
                return False
            
            # Initialize API instances
            self.account_api = lighter.AccountApi(self.api_client)
            self.order_api = lighter.OrderApi(self.api_client)
            self.transaction_api = lighter.TransactionApi(self.api_client)
            self.candlestick_api = lighter.CandlestickApi(self.api_client)
            
            self.connected = True
            logger.info("✅ Connected to Lighter Protocol")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            return False
    
    async def get_market_data(self, symbol: str = 'ETH-USD', market_id: int = 0) -> Dict[str, Any]:
        """
        Get current market data for symbol
        
        Args:
            symbol: Trading pair (e.g., 'ETH-USD')
            market_id: Market ID (default 0 for ETH-USD)
            
        Returns:
            Market data dictionary with price, volume, etc.
        """
        try:
            # Get orderbook details
            result = await self.order_api.order_book_details(market_id=market_id)
            
            if not result or not hasattr(result, 'order_book_details') or not result.order_book_details:
                logger.warning(f"⚠️  No orderbook data for market_id={market_id}")
                return {}
            
            # Get first market from result
            market = result.order_book_details[0]
            
            market_data = {
                'symbol': market.symbol if hasattr(market, 'symbol') else symbol,
                'market_id': market.market_id if hasattr(market, 'market_id') else market_id,
                'last_trade_price': float(market.last_trade_price) if hasattr(market, 'last_trade_price') else 0.0,
                'daily_base_token_volume': float(market.daily_base_token_volume) if hasattr(market, 'daily_base_token_volume') else 0.0,
                'daily_quote_token_volume': float(market.daily_quote_token_volume) if hasattr(market, 'daily_quote_token_volume') else 0.0,
                'daily_price_change': float(market.daily_price_change) if hasattr(market, 'daily_price_change') else 0.0,
                'daily_price_low': float(market.daily_price_low) if hasattr(market, 'daily_price_low') else 0.0,
                'daily_price_high': float(market.daily_price_high) if hasattr(market, 'daily_price_high') else 0.0,
                'open_interest': float(market.open_interest) if hasattr(market, 'open_interest') else 0.0,
                'daily_trades_count': int(market.daily_trades_count) if hasattr(market, 'daily_trades_count') else 0,
                'status': market.status if hasattr(market, 'status') else 'unknown'
            }
            
            return market_data
            
        except Exception as e:
            logger.error(f"❌ Failed to get market data: {e}")
            return {}
    
    async def get_candlesticks(self, market_id: int = 0, resolution: str = '5m', count: int = 100) -> List[Dict[str, Any]]:
        """
        Get candlestick data for technical analysis
        
        Args:
            market_id: Market ID (0 for ETH-USD)
            resolution: Candle resolution ('1m', '5m', '15m', '1h', '4h', '1d')
            count: Number of candles to fetch
            
        Returns:
            List of candle dicts with open, high, low, close, volume, time
        """
        try:
            import time
            
            # Calculate timestamps
            end_timestamp = int(time.time() * 1000)  # Current time in ms
            
            # Calculate start time based on resolution and count
            resolution_ms = {
                '1m': 60_000,
                '5m': 300_000,
                '15m': 900_000,
                '1h': 3_600_000,
                '4h': 14_400_000,
                '1d': 86_400_000
            }
            
            interval_ms = resolution_ms.get(resolution, 300_000)  # Default to 5m
            start_timestamp = end_timestamp - (interval_ms * count)
            
            # Fetch candlestick data
            result = await self.candlestick_api.candlesticks(
                market_id=market_id,
                resolution=resolution,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                count_back=count,
                set_timestamp_to_end=True
            )
            
            if not result or not hasattr(result, 'candlesticks') or not result.candlesticks:
                logger.warning(f"⚠️  No candlestick data for market_id={market_id}, resolution={resolution}")
                return []
            
            # Convert to dict format
            candles = []
            for candle in result.candlesticks:
                candles.append({
                    'time': int(candle.timestamp),
                    'open': float(candle.open),
                    'high': float(candle.high),
                    'low': float(candle.low),
                    'close': float(candle.close),
                    'volume': float(candle.volume0)  # Base token volume
                })
            
            return candles
            
        except Exception as e:
            logger.error(f"❌ Failed to get candlestick data: {e}")
            return []
    
    async def get_multi_timeframe_data(self, market_id: int = 0) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get candlestick data from multiple timeframes
        
        Args:
            market_id: Market ID (0 for ETH-USD)
            
        Returns:
            Dict with timeframes as keys and candle lists as values
        """
        try:
            timeframes = {
                '5m': 100,   # 100 x 5min = ~8 hours
                '15m': 100,  # 100 x 15min = ~25 hours
                '1h': 100,   # 100 x 1hour = ~4 days
                '4h': 50     # 50 x 4hour = ~8 days
            }
            
            multi_tf_data = {}
            
            for tf, count in timeframes.items():
                candles = await self.get_candlesticks(market_id, tf, count)
                if candles:
                    multi_tf_data[tf] = candles
            
            return multi_tf_data
            
        except Exception as e:
            logger.error(f"❌ Failed to get multi-timeframe data: {e}")
            return {}
    
    async def get_account_state(self) -> Dict[str, Any]:
        """
        Get current account state
        
        Returns:
            Account state with balance, margin, positions, etc.
        """
        try:
            # Get account info by index - returns DetailedAccounts with accounts array
            result = await self.account_api.account(by="index", value=str(self.account_index))
            
            if not result.accounts or len(result.accounts) == 0:
                logger.warning("⚠️  No account data returned")
                return {}
            
            # Get first account from result
            account = result.accounts[0]
            
            # Parse balances
            available_balance = float(account.available_balance) if hasattr(account, 'available_balance') else 0.0
            collateral = float(account.collateral) if hasattr(account, 'collateral') else 0.0
            total_asset_value = float(account.total_asset_value) if hasattr(account, 'total_asset_value') else 0.0
            cross_asset_value = float(account.cross_asset_value) if hasattr(account, 'cross_asset_value') else 0.0
            
            # Get asset breakdown
            assets = []
            if hasattr(account, 'additional_properties') and 'assets' in account.additional_properties:
                for asset in account.additional_properties['assets']:
                    assets.append({
                        'symbol': asset.get('symbol'),
                        'balance': float(asset.get('balance', 0)),
                        'locked': float(asset.get('locked_balance', 0))
                    })
            
            # Get positions
            positions = []
            total_margin_used = 0.0
            total_ntl_pos = 0.0
            if hasattr(account, 'positions') and account.positions:
                for pos in account.positions:
                    pos_size = float(pos.position)
                    pos_value = float(pos.position_value)
                    allocated_margin = float(pos.allocated_margin) if hasattr(pos, 'allocated_margin') else 0.0
                    
                    positions.append({
                        'market_id': pos.market_id,
                        'symbol': pos.symbol,
                        'size': pos_size,
                        'avg_entry_price': float(pos.avg_entry_price),
                        'unrealized_pnl': float(pos.unrealized_pnl),
                        'realized_pnl': float(pos.realized_pnl),
                        'position_value': pos_value,
                        'liquidation_price': float(pos.liquidation_price) if pos.liquidation_price else 0.0,
                        'allocated_margin': allocated_margin
                    })
                    
                    # Accumulate totals
                    if pos_size != 0:
                        total_margin_used += allocated_margin
                        total_ntl_pos += abs(pos_value)
            
            account_state = {
                'account_value': collateral,  # Use collateral (total equity including margin in use)
                'available_balance': available_balance,
                'collateral': collateral,
                'total_asset_value': total_asset_value,
                'cross_asset_value': cross_asset_value,
                'total_margin_used': total_margin_used,
                'total_ntl_pos': total_ntl_pos,
                'total_raw_usd': total_asset_value,
                'assets': assets,
                'positions': positions,
                'margin_summary': {
                    'account_value': collateral,
                    'total_margin_used': total_margin_used,
                    'total_ntl_pos': total_ntl_pos
                }
            }
            
            return account_state
            
        except Exception as e:
            logger.error(f"❌ Failed to get account state: {e}")
            return {}
    
    async def get_open_orders(self, market_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get open orders
        
        Args:
            market_id: Optional market ID filter
            
        Returns:
            List of open orders
        """
        try:
            # Get account info which includes active orders - returns DetailedAccounts
            result = await self.account_api.account(by="index", value=str(self.account_index))
            
            if not result.accounts or len(result.accounts) == 0:
                return []
            
            account = result.accounts[0]
            
            orders = []
            if hasattr(account, 'orders') and account.orders:
                for order in account.orders:
                    if market_id is None or getattr(order, 'market_index', -1) == market_id:
                        orders.append({
                            'order_id': getattr(order, 'order_index', ''),
                            'market_id': getattr(order, 'market_index', 0),
                            'side': 'sell' if getattr(order, 'is_ask', False) else 'buy',
                            'size': float(getattr(order, 'base_amount', 0)),
                            'price': float(getattr(order, 'price', 0)),
                            'order_type': getattr(order, 'order_type', ''),
                            'status': getattr(order, 'status', 'open')
                        })
            
            return orders
            
        except Exception as e:
            logger.error(f"❌ Failed to get open orders: {e}")
            return []
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions
        
        Returns:
            List of positions
        """
        try:
            account = await self.account_api.account(by="index", value=str(self.account_index))
            
            positions = []
            if hasattr(account, 'positions') and account.positions:
                for pos in account.positions:
                    positions.append({
                        'symbol': getattr(pos, 'symbol', ''),
                        'market_id': getattr(pos, 'market_index', 0),
                        'size': float(getattr(pos, 'size', 0)),
                        'entry_price': float(getattr(pos, 'entry_price', 0)),
                        'mark_price': float(getattr(pos, 'mark_price', 0)),
                        'liquidation_price': float(getattr(pos, 'liquidation_price', 0)),
                        'unrealized_pnl': float(getattr(pos, 'unrealized_pnl', 0)),
                        'margin': float(getattr(pos, 'margin', 0))
                    })
            
            return positions
            
        except Exception as e:
            logger.error(f"❌ Failed to get positions: {e}")
            return []
    
    async def place_order(self, market_id: int, side: str, order_type: str,
                         size: Decimal, price: Optional[Decimal] = None,
                         reduce_only: bool = False, client_order_id: Optional[int] = None,
                         trigger_price: Optional[Decimal] = None) -> Dict[str, Any]:
        """
        Place an order
        
        Args:
            market_id: Market ID (0 for ETH-USD)
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', 'stop_loss', or 'take_profit'
            size: Order size
            price: Limit price (required for limit orders)
            reduce_only: Whether order is reduce-only
            client_order_id: Client order ID (auto-generated if None)
            trigger_price: Trigger price for stop-loss/take-profit orders
            
        Returns:
            Order result
        """
        try:
            is_ask = (side.lower() == 'sell')
            # SDK uses 10^4 scaling for base_amount (not wei 10^18)
            # Example: 1 ETH = 10000, 0.1 ETH = 1000
            size_float = float(size)
            base_amount = int(size_float * 1e4)
            
            logger.info(f"📤 Placing order: {side.upper()} {size} @ {price or 'MARKET'}")
            logger.info(f"   Size (ETH): {size_float}")
            logger.info(f"   Base amount (10^4): {base_amount}")
            
            # Generate client order ID if not provided
            if client_order_id is None:
                import random
                client_order_id = random.randint(1, 2**32 - 1)
            
            if order_type.lower() == 'market':
                # Get current market price for slippage calculation
                market_data = await self.get_market_data('', market_id)
                current_price = market_data.get('last_price', 0)
                
                # Place market order with slippage limit (1%)
                tx, tx_hash, err = await self.signer_client.create_market_order_limited_slippage(
                    market_index=market_id,
                    client_order_index=client_order_id,
                    base_amount=base_amount,
                    max_slippage=100,  # 1% in basis points
                    is_ask=is_ask,
                    reduce_only=reduce_only,
                    ideal_price=int(current_price * 1e18) if current_price > 0 else None
                )
            elif order_type.lower() == 'stop_loss':
                if trigger_price is None:
                    raise ValueError("Trigger price required for stop-loss orders")
                if price is None:
                    raise ValueError("Price required for stop-loss orders")
                
                trigger_price_scaled = int(float(trigger_price) * 1e2)
                price_scaled = int(float(price) * 1e2)
                
                tx, tx_hash, err = await self.signer_client.create_sl_order(
                    market_index=market_id,
                    client_order_index=client_order_id,
                    base_amount=base_amount,
                    trigger_price=trigger_price_scaled,
                    price=price_scaled,
                    is_ask=is_ask,
                    reduce_only=reduce_only
                )
            elif order_type.lower() == 'take_profit':
                if trigger_price is None:
                    raise ValueError("Trigger price required for take-profit orders")
                if price is None:
                    raise ValueError("Price required for take-profit orders")
                
                trigger_price_scaled = int(float(trigger_price) * 1e2)
                price_scaled = int(float(price) * 1e2)
                
                tx, tx_hash, err = await self.signer_client.create_tp_order(
                    market_index=market_id,
                    client_order_index=client_order_id,
                    base_amount=base_amount,
                    trigger_price=trigger_price_scaled,
                    price=price_scaled,
                    is_ask=is_ask,
                    reduce_only=reduce_only
                )
            else:  # limit order
                if price is None:
                    raise ValueError("Price required for limit orders")
                
                # SDK uses 10^2 scaling for price (supported_price_decimals: 2)
                # Example: $3000.00 = 300000
                price_scaled = int(float(price) * 1e2)
                
                tx, tx_hash, err = await self.signer_client.create_order(
                    market_index=market_id,
                    client_order_index=client_order_id,
                    base_amount=base_amount,
                    price=price_scaled,
                    is_ask=is_ask,
                    order_type=lighter.SignerClient.ORDER_TYPE_LIMIT,
                    time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
                    reduce_only=reduce_only
                )
            
            if err is not None:
                logger.error(f"❌ Order placement failed: {err}")
                return {'error': str(err)}
            
            result = {
                'order_id': client_order_id,
                'tx_hash': tx_hash.tx_hash if hasattr(tx_hash, 'tx_hash') else str(tx_hash),
                'status': 'submitted',
                'market_id': market_id,
                'side': side,
                'size': float(size),
                'price': float(price) if price else None
            }
            
            logger.info(f"✅ Order placed: {result.get('order_id')}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to place order: {e}")
            return {'error': str(e)}
    
    async def cancel_order(self, order_id: int, market_id: int) -> bool:
        """
        Cancel an order
        
        Args:
            order_id: Order ID to cancel
            market_id: Market ID
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"❌ Cancelling order: {order_id}")
            
            tx, tx_hash, err = await self.signer_client.cancel_order(
                market_index=market_id,
                order_index=order_id
            )
            
            if err is not None:
                logger.error(f"❌ Order cancellation failed: {err}")
                return False
            
            logger.info(f"✅ Order cancelled: {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to cancel order: {e}")
            return False
    
    async def cancel_all_orders(self, market_id: Optional[int] = None) -> bool:
        """
        Cancel all open orders
        
        Args:
            market_id: Optional market ID filter
            
        Returns:
            True if successful
        """
        try:
            import time
            
            # Cancel all with GTC time in force
            tx, tx_hash, err = await self.signer_client.cancel_all_orders(
                time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
                time=int(time.time())
            )
            
            if err is not None:
                logger.error(f"❌ Cancel all orders failed: {err}")
                return False
            
            logger.info(f"✅ All orders cancelled")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to cancel all orders: {e}")
            return False
    
    async def close_position(self, market_id: int) -> bool:
        """
        Close position for market
        
        Args:
            market_id: Market ID
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"🔒 Closing position: market {market_id}")
            
            # Get current position
            positions = await self.get_positions()
            position = next((p for p in positions if p.get('market_id') == market_id), None)
            
            if not position:
                logger.warning(f"No position to close for market {market_id}")
                return True
            
            # Place market order to close
            size = abs(Decimal(str(position.get('size', 0))))
            side = 'sell' if position.get('size', 0) > 0 else 'buy'
            
            await self.place_order(
                market_id=market_id,
                side=side,
                order_type='market',
                size=size,
                reduce_only=True
            )
            
            logger.info(f"✅ Position closed: market {market_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to close position: {e}")
            return False
    
    async def get_orderbook(self, market_id: int, depth: int = 10) -> Dict[str, Any]:
        """
        Get orderbook for market
        
        Args:
            market_id: Market ID
            depth: Orderbook depth
            
        Returns:
            Orderbook data
        """
        try:
            orderbook = await self.order_api.order_book_orders(market_id=market_id, limit=depth)
            
            bids = []
            asks = []
            
            if hasattr(orderbook, 'bids') and orderbook.bids:
                bids = [[float(getattr(b, 'price', 0)), float(getattr(b, 'base_amount', 0))] for b in orderbook.bids[:depth]]
            
            if hasattr(orderbook, 'asks') and orderbook.asks:
                asks = [[float(getattr(a, 'price', 0)), float(getattr(a, 'base_amount', 0))] for a in orderbook.asks[:depth]]
            
            return {
                'bids': bids,
                'asks': asks,
                'timestamp': int(getattr(orderbook, 'timestamp', 0))
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get orderbook: {e}")
            return {'bids': [], 'asks': []}
    
    async def get_funding_rate(self, market_id: int) -> Optional[Decimal]:
        """
        Get current funding rate
        
        Args:
            market_id: Market ID
            
        Returns:
            Funding rate as Decimal
        """
        try:
            market_data = await self.get_market_data('', market_id)
            funding_rate = market_data.get('funding_rate', 0)
            return Decimal(str(funding_rate))
            
        except Exception as e:
            logger.error(f"❌ Failed to get funding rate: {e}")
            return None
    
    def is_connected(self) -> bool:
        """Check if connected"""
        return self.connected
    
    async def disconnect(self):
        """Disconnect from Lighter Protocol"""
        try:
            if self.signer_client:
                await self.signer_client.close()
            
            if self.api_client:
                await self.api_client.close()
            
            self.connected = False
            logger.info("✅ Disconnected from Lighter Protocol")
            
        except Exception as e:
            logger.error(f"❌ Error disconnecting: {e}")


if __name__ == "__main__":
    # Test client initialization
    async def test():
        client = LighterClient(
            api_url="https://testnet.zklighter.elliot.ai",
            api_private_key="0xtest",
            api_key_index=0,
            account_index=0
        )
        
        print(f"Client created: {client.is_connected()}")
        await client.connect()
        print(f"Connected: {client.is_connected()}")
        
        if client.is_connected():
            # Test get market data
            market_data = await client.get_market_data('ETH-USD', market_id=0)
            print(f"Market data: {market_data}")
            
            await client.disconnect()
    
    asyncio.run(test())
