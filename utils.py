""""""

Utility functions for Lighter trading botUtility functions and testing tools

"""

- Market metadata resolutionimport asyncio

- Decimal conversion helpersfrom lighter_client import get_client, close_client

- Retry/backoff decoratorsfrom market_data import MarketData

- Order index persistencefrom order_manager import OrderManager

"""from config import settings

import asynciofrom logger import logger

import json

import random

import timeasync def test_connection():

from pathlib import Path    """Test API connection"""

from typing import Optional, Dict, Any, Callable, TypeVar    print("\n=== Testing Lighter API Connection ===\n")

from functools import wraps    

from logger import logger    try:

        client = await get_client()

        print("✓ Client initialized successfully")

# Type variable for async functions        

T = TypeVar('T')        # Test account info

        account_info = await client.get_account_info()

        print(f"✓ Account info retrieved: {account_info}")

class MarketMetadata:        

    """        # Test orderbook

    Store market metadata (decimals, symbol, etc)        orderbooks = await client.get_order_books()

    Populated at startup from exchange API        print(f"✓ Orderbooks retrieved")

    """        

    def __init__(self):        # Test market data

        self.markets: Dict[int, Dict[str, Any]] = {}        market_data = MarketData()

        self.symbol_to_id: Dict[str, int] = {}        mid_price = await market_data.get_mid_price()

            print(f"✓ Current mid price: ${mid_price:.2f}")

    def set_market(self, market_id: int, symbol: str, base_decimals: int,         

                   quote_decimals: int, price_decimals: int, **kwargs):        best_bid, best_ask = await market_data.get_best_bid_ask()

        """Store market metadata"""        print(f"✓ Best bid: ${best_bid:.2f}, Best ask: ${best_ask:.2f}")

        self.markets[market_id] = {        

            'market_id': market_id,        # Test funding rate

            'symbol': symbol,        funding = await market_data.get_funding_rate()

            'base_decimals': base_decimals,        print(f"✓ Funding rate: {funding}")

            'quote_decimals': quote_decimals,        

            'price_decimals': price_decimals,        print("\n✓✓✓ All tests passed! ✓✓✓\n")

            **kwargs        return True

        }        

        self.symbol_to_id[symbol] = market_id    except Exception as e:

            print(f"\n✗ Error: {e}\n")

    def get_market_id(self, symbol: str) -> Optional[int]:        logger.error(f"Connection test failed: {e}", exc_info=True)

        """Get market ID from symbol"""        return False

        return self.symbol_to_id.get(symbol)    finally:

            await close_client()

    def get_market(self, market_id: int) -> Optional[Dict[str, Any]]:

        """Get market metadata by ID"""

        return self.markets.get(market_id)async def get_account_status():

        """Display account status"""

    def get_base_decimals(self, market_id: int) -> int:    print("\n=== Account Status ===\n")

        """Get base decimals for market (default 6 if not found)"""    

        market = self.markets.get(market_id)    try:

        return market.get('base_decimals', 6) if market else 6        order_manager = OrderManager()

            

    def get_price_decimals(self, market_id: int) -> int:        # Account info

        """Get price decimals for market (default 2 if not found)"""        account_info = await order_manager.get_account_info()

        market = self.markets.get(market_id)        print(f"Account: {account_info}")

        return market.get('price_decimals', 2) if market else 2        

            # Positions

    def to_base_amount(self, size: float, market_id: int) -> int:        positions = await order_manager.get_positions()

        """        print(f"\nOpen Positions: {len(positions)}")

        Convert human-readable size to exchange base units        for pos in positions:

                    side = "LONG" if pos.is_long else "SHORT"

        Example: size=0.001 BTC with 6 decimals → 1000            print(f"  Market {pos.market_id}: {side} {abs(pos.size)}")

        """            print(f"    Entry: ${pos.entry_price:.2f}, Mark: ${pos.mark_price:.2f}")

        decimals = self.get_base_decimals(market_id)            print(f"    PnL: ${pos.unrealized_pnl:.2f} ({pos.pnl_percentage:.2f}%)")

        multiplier = 10 ** decimals        

        return int(size * multiplier)        # Active orders

            orders = await order_manager.get_active_orders()

    def from_base_amount(self, amount: int, market_id: int) -> float:        print(f"\nActive Orders: {len(orders)}")

        """        for order in orders:

        Convert exchange base units to human-readable size            print(f"  {order.side} {order.size} @ {order.price or 'MARKET'}")

                

        Example: amount=1000 with 6 decimals → 0.001 BTC    except Exception as e:

        """        print(f"Error: {e}")

        decimals = self.get_base_decimals(market_id)        logger.error(f"Failed to get account status: {e}", exc_info=True)

        divider = 10 ** decimals    finally:

        return amount / divider        await close_client()

    

    def to_price_int(self, price: float, market_id: int) -> int:

        """async def get_market_info():

        Convert human-readable price to exchange price units    """Display market information"""

            print("\n=== Market Information ===\n")

        Example: price=3500.50 with 2 decimals → 350050    

        """    try:

        decimals = self.get_price_decimals(market_id)        market_data = MarketData()

        multiplier = 10 ** decimals        

        return int(price * multiplier)        # Market summary

            summary = await market_data.get_market_summary()

    def from_price_int(self, price_int: int, market_id: int) -> float:        print(f"Market ID: {summary.get('market_id', settings.trading_market_id)}")

        """        print(f"Mid Price: ${summary.get('mid_price', 0):.2f}")

        Convert exchange price units to human-readable price        print(f"Best Bid: ${summary.get('best_bid', 0):.2f}")

                print(f"Best Ask: ${summary.get('best_ask', 0):.2f}")

        Example: price_int=350050 with 2 decimals → 3500.50        print(f"Spread: {summary.get('spread_bps', 0):.2f} bps")

        """        print(f"Funding Rate: {summary.get('funding_rate', 0):.6f}")

        decimals = self.get_price_decimals(market_id)        print(f"Recent Trades: {summary.get('recent_trades_count', 0)}")

        divider = 10 ** decimals        

        return price_int / divider        # Orderbook depth

        depth = summary.get('orderbook_depth', {})

        print(f"\nOrderbook Depth:")

# Global market metadata instance        print(f"  Bids: {depth.get('bids', 0)} levels")

market_metadata = MarketMetadata()        print(f"  Asks: {depth.get('asks', 0)} levels")

        

    except Exception as e:

class OrderIndexer:        print(f"Error: {e}")

    """        logger.error(f"Failed to get market info: {e}", exc_info=True)

    Persist client_order_index to avoid duplicate orders on restart    finally:

    """        await close_client()

    def __init__(self, filepath: str = "data/order_index.json"):

        self.filepath = Path(filepath)

        self.filepath.parent.mkdir(parents=True, exist_ok=True)async def place_test_order():

        self.current_index = self._load()    """Place a small test order"""

        self.lock = asyncio.Lock()    print("\n=== Placing Test Order ===\n")

        

    def _load(self) -> int:    try:

        """Load last order index from file"""        market_data = MarketData()

        if self.filepath.exists():        order_manager = OrderManager()

            try:        

                with open(self.filepath, 'r') as f:        # Get current price

                    data = json.load(f)        mid_price = await market_data.get_mid_price()

                    index = data.get('last_index', 0)        print(f"Current mid price: ${mid_price:.2f}")

                    logger.info(f"Loaded last order index: {index}")        

                    return index        # Place a small limit buy order 5% below market

            except Exception as e:        test_price = mid_price * 0.95

                logger.error(f"Error loading order index: {e}")        test_size = 0.001  # Very small size for testing

                return 0        

        return 0        print(f"\nPlacing limit BUY order:")

            print(f"  Size: {test_size}")

    def _save(self, index: int):        print(f"  Price: ${test_price:.2f}")

        """Save order index to file"""        

        try:        order = await order_manager.place_limit_order(

            with open(self.filepath, 'w') as f:            side="buy",

                json.dump({            size=test_size,

                    'last_index': index,            price=test_price

                    'timestamp': time.time()        )

                }, f, indent=2)        

        except Exception as e:        if order:

            logger.error(f"Error saving order index: {e}")            print(f"\n✓ Order placed successfully!")

                print(f"  Client Order Index: {order.client_order_index}")

    async def get_next(self) -> int:        else:

        """Get next order index atomically"""            print("\n✗ Failed to place order")

        async with self.lock:        

            self.current_index += 1    except Exception as e:

            self._save(self.current_index)        print(f"\nError: {e}")

            return self.current_index        logger.error(f"Failed to place test order: {e}", exc_info=True)

        finally:

    async def peek(self) -> int:        await close_client()

        """Get current index without incrementing"""

        async with self.lock:

            return self.current_indexasync def cancel_all_orders():

    """Cancel all open orders"""

    print("\n=== Cancelling All Orders ===\n")

# Global order indexer    

order_indexer = OrderIndexer()    try:

        order_manager = OrderManager()

        

def retry_async(        # Get current orders

    max_attempts: int = 3,        orders = await order_manager.get_active_orders()

    initial_delay: float = 1.0,        print(f"Current active orders: {len(orders)}")

    max_delay: float = 30.0,        

    exponential_base: float = 2.0,        if len(orders) == 0:

    jitter: bool = True,            print("No orders to cancel")

    exceptions: tuple = (Exception,)            return

):        

    """        # Cancel all

    Retry decorator with exponential backoff and jitter        success = await order_manager.cancel_all_orders()

            

    Args:        if success:

        max_attempts: Maximum number of retry attempts            print("✓ All orders cancelled successfully")

        initial_delay: Initial delay in seconds        else:

        max_delay: Maximum delay in seconds            print("✗ Failed to cancel orders")

        exponential_base: Base for exponential backoff        

        jitter: Add random jitter to delays    except Exception as e:

        exceptions: Tuple of exceptions to catch        print(f"Error: {e}")

            logger.error(f"Failed to cancel orders: {e}", exc_info=True)

    Usage:    finally:

        @retry_async(max_attempts=3)        await close_client()

        async def fetch_data():

            ...

    """def show_menu():

    def decorator(func: Callable[..., T]) -> Callable[..., T]:    """Show interactive menu"""

        @wraps(func)    print("\n" + "="*50)

        async def wrapper(*args, **kwargs) -> T:    print("Lighter Trading Bot - Utilities")

            attempt = 0    print("="*50)

            while attempt < max_attempts:    print("\n1. Test API Connection")

                try:    print("2. Show Account Status")

                    return await func(*args, **kwargs)    print("3. Show Market Info")

                except exceptions as e:    print("4. Place Test Order")

                    attempt += 1    print("5. Cancel All Orders")

                    if attempt >= max_attempts:    print("0. Exit")

                        logger.error(    print()

                            f"Function {func.__name__} failed after {max_attempts} attempts",

                            exc_info=True

                        )async def main():

                        raise    """Main utility menu"""

                        while True:

                    # Calculate delay with exponential backoff        show_menu()

                    delay = min(        

                        initial_delay * (exponential_base ** (attempt - 1)),        try:

                        max_delay            choice = input("Select option: ").strip()

                    )            

                                if choice == "0":

                    # Add jitter                print("Exiting...")

                    if jitter:                break

                        delay = delay * (0.5 + random.random())            elif choice == "1":

                                    await test_connection()

                    logger.warning(            elif choice == "2":

                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}), "                await get_account_status()

                        f"retrying in {delay:.2f}s: {e}"            elif choice == "3":

                    )                await get_market_info()

                    await asyncio.sleep(delay)            elif choice == "4":

                            await place_test_order()

            # Should never reach here            elif choice == "5":

            raise RuntimeError(f"Retry logic error in {func.__name__}")                await cancel_all_orders()

                    else:

        return wrapper                print("Invalid option")

    return decorator            

            input("\nPress Enter to continue...")

            

async def resolve_market_metadata(client, symbol: str) -> Optional[int]:        except KeyboardInterrupt:

    """            print("\nExiting...")

    Resolve market metadata from exchange            break

            except Exception as e:

    Returns:            print(f"Error: {e}")

        market_id if found, None otherwise            logger.error(f"Menu error: {e}", exc_info=True)

    

    This should be called at startup to populate market_metadata

    """if __name__ == "__main__":

    try:    asyncio.run(main())

        # Try to get exchange stats which includes market info
        logger.info(f"Resolving market metadata for {symbol}...")
        
        # Fallback: Use known markets for Lighter
        # BTC-PERP is market_id=0, uses 6 decimals for base, 2 for price
        known_markets = {
            'BTC-PERP': {'id': 0, 'base_decimals': 6, 'price_decimals': 2},
            'ETH-PERP': {'id': 1, 'base_decimals': 6, 'price_decimals': 2},
            'NEAR-PERP': {'id': 2, 'base_decimals': 6, 'price_decimals': 2},
        }
        
        if symbol in known_markets:
            info = known_markets[symbol]
            market_metadata.set_market(
                market_id=info['id'],
                symbol=symbol,
                base_decimals=info['base_decimals'],
                quote_decimals=6,
                price_decimals=info['price_decimals']
            )
            logger.info(
                f"✓ Registered market {symbol} → ID {info['id']} "
                f"(base_decimals={info['base_decimals']}, price_decimals={info['price_decimals']})"
            )
            return info['id']
        
        logger.error(f"Unknown market symbol: {symbol}")
        logger.error(f"Known markets: {list(known_markets.keys())}")
        return None
        
    except Exception as e:
        logger.error(f"Error resolving market metadata: {e}", exc_info=True)
        return None


def format_size(size: float, decimals: int = 4) -> str:
    """Format size for display"""
    return f"{size:.{decimals}f}".rstrip('0').rstrip('.')


def format_price(price: float, decimals: int = 2) -> str:
    """Format price for display"""
    return f"${price:,.{decimals}f}"


def format_pnl(pnl: float) -> str:
    """Format P&L with color indicators"""
    sign = "+" if pnl >= 0 else ""
    return f"{sign}${pnl:,.2f}"
