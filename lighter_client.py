"""
Lighter API Client using official lighter-python SDK
"""
import lighter
import asyncio
from typing import Dict, Any, Optional, List
from config import settings
from logger import logger
from utils import retry_async, resolve_market_metadata
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
    @retry_async(max_attempts=settings.api_retry_limit)
    async def get_order_books(self, market_id: Optional[int] = None) -> Dict[str, Any]:
        """Get order books"""
        try:
            result = await self.order_api.order_books(market_id=market_id or 255)
            return result.to_dict() if hasattr(result, 'to_dict') else result
        except Exception as e:
            logger.error(f"Error getting order books: {e}")
            raise  # Let retry_async handle this
    
    @retry_async(max_attempts=settings.api_retry_limit)
    async def get_order_book_details(self, market_id: int) -> Dict[str, Any]:
        """Get order book details for specific market"""
        try:
            result = await self.order_api.order_book_details(market_id=market_id)
            return result.to_dict() if hasattr(result, 'to_dict') else result
        except Exception as e:
            logger.error(f"Error getting order book details: {e}")
            raise  # Let retry_async handle this
    
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
    
    @retry_async(max_attempts=settings.api_retry_limit)
    async def get_candlesticks(self, market_id: int, resolution: str = "1h", limit: int = 100) -> List[Dict]:
        """Get candlestick data"""
        try:
            result = await self.candlestick_api.candlesticks(
                market_id=market_id,
                resolution=resolution,
                limit=limit
            )
            if hasattr(result, 'candlesticks'):
                return [c.to_dict() if hasattr(c, 'to_dict') else c for c in result.candlesticks]
            return []
        except Exception as e:
            logger.error(f"Error getting candlesticks: {e}")
            raise  # Let retry_async handle this
    
    @retry_async(max_attempts=settings.api_retry_limit)
    async def get_funding_rates(self, market_id: Optional[int] = None) -> List[Dict]:
        """Get funding rates"""
        try:
            result = await self.candlestick_api.fundings(market_id=market_id or 255, limit=10)
            if hasattr(result, 'fundings'):
                return [f.to_dict() if hasattr(f, 'to_dict') else f for f in result.fundings]
            return []
        except Exception as e:
            logger.error(f"Error getting funding rates: {e}")
            raise  # Let retry_async handle this
    
    # Account Methods
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
        """Create a limit order"""
        try:
            return await self.signer_client.create_order(
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
        """Create a market order"""
        try:
            return await self.signer_client.create_market_order(
                market_index=market_index,
                client_order_index=client_order_index,
                base_amount=base_amount,
                avg_execution_price=avg_execution_price,
                is_ask=is_ask,
                reduce_only=reduce_only
            )
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
