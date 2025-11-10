"""
Utility functions and testing tools
"""
import asyncio
from lighter_client import get_client, close_client
from market_data import MarketData
from order_manager import OrderManager
from config import settings
from logger import logger


async def test_connection():
    """Test API connection"""
    print("\n=== Testing Lighter API Connection ===\n")
    
    try:
        client = await get_client()
        print("✓ Client initialized successfully")
        
        # Test account info
        account_info = await client.get_account_info()
        print(f"✓ Account info retrieved: {account_info}")
        
        # Test orderbook
        orderbooks = await client.get_order_books()
        print(f"✓ Orderbooks retrieved")
        
        # Test market data
        market_data = MarketData()
        mid_price = await market_data.get_mid_price()
        print(f"✓ Current mid price: ${mid_price:.2f}")
        
        best_bid, best_ask = await market_data.get_best_bid_ask()
        print(f"✓ Best bid: ${best_bid:.2f}, Best ask: ${best_ask:.2f}")
        
        # Test funding rate
        funding = await market_data.get_funding_rate()
        print(f"✓ Funding rate: {funding}")
        
        print("\n✓✓✓ All tests passed! ✓✓✓\n")
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        logger.error(f"Connection test failed: {e}", exc_info=True)
        return False
    finally:
        await close_client()


async def get_account_status():
    """Display account status"""
    print("\n=== Account Status ===\n")
    
    try:
        order_manager = OrderManager()
        
        # Account info
        account_info = await order_manager.get_account_info()
        print(f"Account: {account_info}")
        
        # Positions
        positions = await order_manager.get_positions()
        print(f"\nOpen Positions: {len(positions)}")
        for pos in positions:
            side = "LONG" if pos.is_long else "SHORT"
            print(f"  Market {pos.market_id}: {side} {abs(pos.size)}")
            print(f"    Entry: ${pos.entry_price:.2f}, Mark: ${pos.mark_price:.2f}")
            print(f"    PnL: ${pos.unrealized_pnl:.2f} ({pos.pnl_percentage:.2f}%)")
        
        # Active orders
        orders = await order_manager.get_active_orders()
        print(f"\nActive Orders: {len(orders)}")
        for order in orders:
            print(f"  {order.side} {order.size} @ {order.price or 'MARKET'}")
        
    except Exception as e:
        print(f"Error: {e}")
        logger.error(f"Failed to get account status: {e}", exc_info=True)
    finally:
        await close_client()


async def get_market_info():
    """Display market information"""
    print("\n=== Market Information ===\n")
    
    try:
        market_data = MarketData()
        
        # Market summary
        summary = await market_data.get_market_summary()
        print(f"Market ID: {summary.get('market_id', settings.trading_market_id)}")
        print(f"Mid Price: ${summary.get('mid_price', 0):.2f}")
        print(f"Best Bid: ${summary.get('best_bid', 0):.2f}")
        print(f"Best Ask: ${summary.get('best_ask', 0):.2f}")
        print(f"Spread: {summary.get('spread_bps', 0):.2f} bps")
        print(f"Funding Rate: {summary.get('funding_rate', 0):.6f}")
        print(f"Recent Trades: {summary.get('recent_trades_count', 0)}")
        
        # Orderbook depth
        depth = summary.get('orderbook_depth', {})
        print(f"\nOrderbook Depth:")
        print(f"  Bids: {depth.get('bids', 0)} levels")
        print(f"  Asks: {depth.get('asks', 0)} levels")
        
    except Exception as e:
        print(f"Error: {e}")
        logger.error(f"Failed to get market info: {e}", exc_info=True)
    finally:
        await close_client()


async def place_test_order():
    """Place a small test order"""
    print("\n=== Placing Test Order ===\n")
    
    try:
        market_data = MarketData()
        order_manager = OrderManager()
        
        # Get current price
        mid_price = await market_data.get_mid_price()
        print(f"Current mid price: ${mid_price:.2f}")
        
        # Place a small limit buy order 5% below market
        test_price = mid_price * 0.95
        test_size = 0.001  # Very small size for testing
        
        print(f"\nPlacing limit BUY order:")
        print(f"  Size: {test_size}")
        print(f"  Price: ${test_price:.2f}")
        
        order = await order_manager.place_limit_order(
            side="buy",
            size=test_size,
            price=test_price
        )
        
        if order:
            print(f"\n✓ Order placed successfully!")
            print(f"  Client Order Index: {order.client_order_index}")
        else:
            print("\n✗ Failed to place order")
        
    except Exception as e:
        print(f"\nError: {e}")
        logger.error(f"Failed to place test order: {e}", exc_info=True)
    finally:
        await close_client()


async def cancel_all_orders():
    """Cancel all open orders"""
    print("\n=== Cancelling All Orders ===\n")
    
    try:
        order_manager = OrderManager()
        
        # Get current orders
        orders = await order_manager.get_active_orders()
        print(f"Current active orders: {len(orders)}")
        
        if len(orders) == 0:
            print("No orders to cancel")
            return
        
        # Cancel all
        success = await order_manager.cancel_all_orders()
        
        if success:
            print("✓ All orders cancelled successfully")
        else:
            print("✗ Failed to cancel orders")
        
    except Exception as e:
        print(f"Error: {e}")
        logger.error(f"Failed to cancel orders: {e}", exc_info=True)
    finally:
        await close_client()


def show_menu():
    """Show interactive menu"""
    print("\n" + "="*50)
    print("Lighter Trading Bot - Utilities")
    print("="*50)
    print("\n1. Test API Connection")
    print("2. Show Account Status")
    print("3. Show Market Info")
    print("4. Place Test Order")
    print("5. Cancel All Orders")
    print("0. Exit")
    print()


async def main():
    """Main utility menu"""
    while True:
        show_menu()
        
        try:
            choice = input("Select option: ").strip()
            
            if choice == "0":
                print("Exiting...")
                break
            elif choice == "1":
                await test_connection()
            elif choice == "2":
                await get_account_status()
            elif choice == "3":
                await get_market_info()
            elif choice == "4":
                await place_test_order()
            elif choice == "5":
                await cancel_all_orders()
            else:
                print("Invalid option")
            
            input("\nPress Enter to continue...")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            logger.error(f"Menu error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
