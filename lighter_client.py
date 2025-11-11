"""
Lighter API Client using official lighter-python SDK
"""
import lighter
import asyncio
from typing import Dict, Any, Optional, List
from config import settings
from logger import logger
from utils import retry_async, resolve_market_metadata, circuit_breaker, lighter_api_breaker
import eth_account


class LighterClient:
    """
    Wrapper for Lighter official Python SDK
    Provides simplified interface for trading bot
    """

    def __init__(self):
        # placeholders filled by async create()
        self.signer_client: Optional[lighter.SignerClient] = None
        self.config: Optional[lighter.Configuration] = None
        self.api_client: Optional[lighter.ApiClient] = None
        self.account_api = None
        self.order_api = None
        self.transaction_api = None
        self.candlestick_api = None

    @classmethod
    async def create(cls) -> "LighterClient":
        """Async initializer that can query account info when needed."""
        self = cls()

        # create API client first (used for lookups)
        self.config = lighter.Configuration(host=settings.lighter_base_url)
        self.api_client = lighter.ApiClient(configuration=self.config)

        # API instances
        self.account_api = lighter.AccountApi(self.api_client)
        self.order_api = lighter.OrderApi(self.api_client)
        self.transaction_api = lighter.TransactionApi(self.api_client)
        self.candlestick_api = lighter.CandlestickApi(self.api_client)

        # If account index is missing, try to discover it using an ETH private key if provided
        if settings.lighter_account_index is None and getattr(settings, 'lighter_eth_private_key', None):
            try:
                eth_key = settings.lighter_eth_private_key
                eth_key_pref = eth_key if eth_key.startswith('0x') else f'0x{eth_key}'
                eth_acc = eth_account.Account.from_key(eth_key_pref)
                eth_address = eth_acc.address
                resp = await self.account_api.accounts_by_l1_address(l1_address=eth_address)
                if resp and getattr(resp, 'sub_accounts', None):
                    # pick the first sub-account index
                    settings.lighter_account_index = resp.sub_accounts[0].index
                    logger.info(f"Discovered account_index={settings.lighter_account_index} for address {eth_address}")
                else:
                    logger.warning(f"No sub-accounts found for {eth_address}")
            except Exception as e:
                logger.warning(f" failed to discover account index via ETH key: {e}")

        # Initialize signer client (SignerClient may perform internal checks)
        try:
            self.signer_client = lighter.SignerClient(
                url=settings.lighter_base_url,
                private_key=settings.lighter_api_key_private_key,
                account_index=settings.lighter_account_index or 0,
                api_key_index=settings.lighter_api_key_index,
            )

            # perform a quick client check
            err = self.signer_client.check_client()
            if err:
                raise Exception(err)

        except Exception as e:
            # close api_client session cleanly
            try:
                await self.api_client.close()
            except Exception:
                pass
            # Provide actionable guidance
            msg = (
                f"Signer client initialization failed: {e}\n"
                "Possible causes:\n"
                " - LIGHTER_ACCOUNT_INDEX is missing/incorrect. It must be an integer (0,1,2...).\n"
                " - LIGHTER_API_KEY_PRIVATE_KEY is not the correct API key private value.\n"
                " - LIGHTER_API_KEY_INDEX is wrong (default is 253 or the index you created).\n"
                "Fix options:\n"
                "  * Set LIGHTER_ACCOUNT_INDEX=<your-account-number> in .env (get it from app.lighter.xyz 'Accounts').\n"
                "  * If you have your Ethereum private key, set LIGHTER_ETH_PRIVATE_KEY and rerun; the client will attempt to discover the account index.\n"
                "  * Verify your LIGHTER_API_KEY_PRIVATE_KEY is exactly the API key private part (hex).\n"
            )
            raise Exception(msg)

        return self
    
    async def close(self):
        """Close all connections"""
        await self.signer_client.close()
        await self.api_client.close()
    
    # Market Data Methods
    @circuit_breaker(breaker=lighter_api_breaker)
    @retry_async(max_attempts=settings.api_retry_limit)
    async def get_order_books(self, market_id: Optional[int] = None) -> Dict[str, Any]:
        """Get order books"""
        try:
            result = await self.order_api.order_books(market_id=market_id or settings.trading_market_id)
            return result.to_dict() if hasattr(result, 'to_dict') else result
        except Exception as e:
            logger.error(f"Error getting order books: {e}")
            raise  # Let retry_async handle this
    
    @circuit_breaker(breaker=lighter_api_breaker)
    @retry_async(max_attempts=settings.api_retry_limit)
    async def get_order_book_details(self, market_id: int) -> Dict[str, Any]:
        """Get order book details for specific market"""
        try:
            result = await self.order_api.order_book_details(market_id=market_id)
            return result.to_dict() if hasattr(result, 'to_dict') else result
        except Exception as e:
            logger.error(f"Error getting order book details: {e}")
            raise  # Let retry_async handle this
    
    @circuit_breaker(breaker=lighter_api_breaker)
    @retry_async(max_attempts=settings.api_retry_limit)
    async def get_recent_trades(self, market_id: int, limit: int = 100) -> List[Dict]:
        """Get recent trades"""
        try:
            result = await self.order_api.recent_trades(market_id=market_id, limit=limit)
            if hasattr(result, 'trades'):
                return [t.to_dict() if hasattr(t, 'to_dict') else t for t in result.trades]
            return []
        except Exception as e:
            logger.error(f"Error getting recent trades: {e}")
            raise  # Let retry_async handle this
    
    @circuit_breaker(breaker=lighter_api_breaker)
    @retry_async(max_attempts=settings.api_retry_limit)
    async def get_candlesticks(self, market_id: int, resolution: str = "1h", limit: int = 100) -> List[Dict]:
        """
        Get candlestick data
        
        Args:
            market_id: Market ID
            resolution: Timeframe (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles (count_back)
        """
        try:
            import time
            # SDK requires start_timestamp, end_timestamp, and count_back
            end_timestamp = int(time.time())  # Current time
            start_timestamp = end_timestamp - (limit * self._get_resolution_seconds(resolution))
            
            result = await self.candlestick_api.candlesticks(
                market_id=market_id,
                resolution=resolution,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                count_back=limit
            )
            if hasattr(result, 'candlesticks'):
                return [c.to_dict() if hasattr(c, 'to_dict') else c for c in result.candlesticks]
            return []
        except Exception as e:
            logger.error(f"Error getting candlesticks: {e}")
            raise  # Let retry_async handle this
    
    def _get_resolution_seconds(self, resolution: str) -> int:
        """
        Convert resolution string to seconds
        
        Note: This is a utility helper map for time conversions.
        The resolution values themselves (1m, 5m, etc.) are defined by the API specification.
        """
        resolution_map = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
        }
        return resolution_map.get(resolution, 3600)
    
    @circuit_breaker(breaker=lighter_api_breaker)
    @retry_async(max_attempts=settings.api_retry_limit)
    async def get_funding_rates(self, market_id: Optional[int] = None, limit: int = 10) -> List[Dict]:
        """
        Get funding rates
        
        Args:
            market_id: Market ID (default from settings)
            limit: Number of funding rate records
        """
        try:
            import time
            # SDK requires resolution, start_timestamp, end_timestamp, and count_back
            # API only supports "1h" or "1d" for funding rates
            end_timestamp = int(time.time())
            start_timestamp = end_timestamp - (limit * 3600)  # 1h periods
            
            result = await self.candlestick_api.fundings(
                market_id=market_id or settings.trading_market_id,
                resolution="1h",  # API only supports 1h or 1d
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                count_back=limit
            )
            if hasattr(result, 'fundings'):
                return [f.to_dict() if hasattr(f, 'to_dict') else f for f in result.fundings]
            return []
        except Exception as e:
            logger.error(f"Error getting funding rates: {e}")
            raise  # Let retry_async handle this
    
    # Account Methods
    @circuit_breaker(breaker=lighter_api_breaker)
    @retry_async(max_attempts=settings.api_retry_limit)
    async def get_account_info(self, account_index: Optional[int] = None) -> Dict[str, Any]:
        """Get account information"""
        try:
            acc_idx = account_index or settings.lighter_account_index
            result = await self.account_api.account(by="index", value=str(acc_idx))
            return result.to_dict() if hasattr(result, 'to_dict') else result
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            raise  # Let retry_async handle this
    
    async def get_balances(self, account_index: Optional[int] = None) -> Dict[str, Any]:
        """Get account balances"""
        return await self.get_account_info(account_index)
    
    async def get_positions(self, account_index: Optional[int] = None) -> List[Dict]:
        """Get all positions"""
        try:
            acc_idx = account_index or settings.lighter_account_index
            account_info = await self.get_account_info(acc_idx)
            if 'positions' in account_info:
                return account_info['positions']
            return []
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    # Order Methods
    @circuit_breaker(breaker=lighter_api_breaker)
    @retry_async(max_attempts=settings.api_retry_limit)
    async def get_active_orders(self, market_id: int, account_index: Optional[int] = None) -> List[Dict]:
        """Get active orders"""
        try:
            acc_idx = account_index or settings.lighter_account_index
            auth_token, err = self.signer_client.create_auth_token_with_expiry()
            if err:
                logger.error(f"Error creating auth token: {err}")
                return []
            
            result = await self.order_api.account_active_orders(
                account_index=acc_idx,
                market_id=market_id,
                authorization=auth_token,
                auth=auth_token
            )
            if hasattr(result, 'orders'):
                return [o.to_dict() if hasattr(o, 'to_dict') else o for o in result.orders]
            return []
        except Exception as e:
            logger.error(f"Error getting active orders: {e}")
            raise  # Let retry_async handle this
    
    async def create_limit_order(
        self,
        market_index: int,
        client_order_index: int,
        base_amount: int,  # In smallest units (e.g., 100000 = 0.1 ETH)
        price: int,  # In smallest units
        is_ask: bool,  # True for sell, False for buy
        reduce_only: bool = False
    ) -> tuple[Any, Any, Optional[str]]:
        """
        Create a limit order
        
        IMPORTANT: SDK create_order returns (CreateOrder, TxHash, error_str)
        """
        try:
            result = await self.signer_client.create_order(
                market_index=market_index,
                client_order_index=client_order_index,
                base_amount=base_amount,
                price=price,
                is_ask=is_ask,
                order_type=lighter.SignerClient.ORDER_TYPE_LIMIT,
                time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
                reduce_only=reduce_only,
                trigger_price=0
            )
            # Unpack: (CreateOrder object, TxHash object, error_str)
            create_order_obj, tx_hash_obj, error_str = result
            return create_order_obj, tx_hash_obj, error_str
        except Exception as e:
            logger.error(f"Error creating limit order: {e}")
            return None, None, str(e)
    
    async def create_market_order(
        self,
        market_index: int,
        client_order_index: int,
        base_amount: int,
        avg_execution_price: int,  # Worst acceptable price
        is_ask: bool,
        reduce_only: bool = False
    ) -> tuple[Any, Any, Optional[str]]:
        """
        Create a market order
        
        IMPORTANT: SDK returns (CreateOrder, TxHash, error_str), NOT (tx_info, tx_hash, error)
        """
        try:
            result = await self.signer_client.create_market_order(
                market_index=market_index,
                client_order_index=client_order_index,
                base_amount=base_amount,
                avg_execution_price=avg_execution_price,
                is_ask=is_ask,
                reduce_only=reduce_only
            )
            # Unpack: (CreateOrder object, TxHash object, error_str)
            create_order_obj, tx_hash_obj, error_str = result
            return create_order_obj, tx_hash_obj, error_str
        except Exception as e:
            logger.error(f"Error creating market order: {e}")
            return None, None, str(e)
    
    async def cancel_order(self, market_index: int, order_index: int) -> tuple[Any, Any, Optional[str]]:
        """Cancel a specific order"""
        try:
            return await self.signer_client.cancel_order(
                market_index=market_index,
                order_index=order_index
            )
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return None, None, str(e)
    
    async def cancel_all_orders(self) -> tuple[Any, Any, Optional[str]]:
        """Cancel all orders"""
        try:
            return await self.signer_client.cancel_all_orders(
                time_in_force=lighter.SignerClient.CANCEL_ALL_TIF_IMMEDIATE,
                time=0
            )
        except Exception as e:
            logger.error(f"Error cancelling all orders: {e}")
            return None, None, str(e)

    # --- Advanced Order Types wrappers (stop-loss, take-profit, grouped OCO) ---

    async def create_stop_loss(self, market_index: int, client_order_index: int, base_amount: int, trigger_price: int, price: int, is_ask: bool, reduce_only: bool = True) -> tuple[Any, Any, Optional[str]]:
        """Create a stop-loss limit order."""
        try:
            return await self.signer_client.create_sl_limit_order(
                market_index=market_index,
                client_order_index=client_order_index,
                base_amount=base_amount,
                trigger_price=trigger_price,
                price=price,
                is_ask=is_ask,
                reduce_only=reduce_only,
            )
        except Exception as e:
            logger.error(f"Error creating stop-loss order: {e}")
            return None, None, str(e)

    async def create_take_profit(self, market_index: int, client_order_index: int, base_amount: int, trigger_price: int, price: int, is_ask: bool, reduce_only: bool = True) -> tuple[Any, Any, Optional[str]]:
        """Create a take-profit limit order."""
        try:
            return await self.signer_client.create_tp_limit_order(
                market_index=market_index,
                client_order_index=client_order_index,
                base_amount=base_amount,
                trigger_price=trigger_price,
                price=price,
                is_ask=is_ask,
                reduce_only=reduce_only,
            )
        except Exception as e:
            logger.error(f"Error creating take-profit order: {e}")
            return None, None, str(e)

    async def create_oco_orders(self, market_index: int, client_order_index_tp: int, client_order_index_sl: int, base_amount: int, tp_price: int, sl_price: int, sl_trigger: int, tp_trigger: int, is_ask: bool, reduce_only: bool = True) -> tuple[Any, Any, Optional[str]]:
        """Create a One-Cancels-the-Other grouped order (TP + SL)."""
        try:
            from lighter.signer_client import CreateOrderTxReq
            take_profit = CreateOrderTxReq(
                MarketIndex=market_index,
                ClientOrderIndex=client_order_index_tp,
                BaseAmount=base_amount,
                Price=tp_price,
                IsAsk=int(is_ask),
                Type=lighter.SignerClient.ORDER_TYPE_TAKE_PROFIT_LIMIT,
                TimeInForce=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
                ReduceOnly=int(reduce_only),
                TriggerPrice=tp_trigger,
                OrderExpiry=lighter.SignerClient.DEFAULT_28_DAY_ORDER_EXPIRY,
            )
            stop_loss = CreateOrderTxReq(
                MarketIndex=market_index,
                ClientOrderIndex=client_order_index_sl,
                BaseAmount=base_amount,
                Price=sl_price,
                IsAsk=int(is_ask),
                Type=lighter.SignerClient.ORDER_TYPE_STOP_LOSS_LIMIT,
                TimeInForce=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
                ReduceOnly=int(reduce_only),
                TriggerPrice=sl_trigger,
                OrderExpiry=lighter.SignerClient.DEFAULT_28_DAY_ORDER_EXPIRY,
            )
            return await self.signer_client.create_grouped_orders(
                grouping_type=lighter.SignerClient.GROUPING_TYPE_ONE_CANCELS_THE_OTHER,
                orders=[take_profit, stop_loss],
            )
        except Exception as e:
            logger.error(f"Error creating OCO orders: {e}")
            return None, None, str(e)


# Global client instance
_client: Optional[LighterClient] = None


async def get_client() -> LighterClient:
    """Get or create global client instance (async)"""
    global _client
    if _client is None:
        _client = await LighterClient.create()
    return _client


async def close_client():
    """Close global client"""
    global _client
    if _client:
        await _client.close()
        _client = None
