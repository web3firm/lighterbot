"""
Simple test script for Lighter API
"""
import asyncio
import pytest
from lighter_client import get_client, close_client
from config import settings


@pytest.mark.asyncio
async def test():
    print(f"\n=== Testing Lighter API ===")
    print(f"URL: {settings.lighter_base_url}")
    print(f"Market ID: {settings.trading_market_id}")
    print(f"Account Index: {settings.lighter_account_index}\n")
    
    try:
        # Initialize client
        client = await get_client()
        print("✓ Client initialized")
        
        # Test account
        account = await client.get_account_info()
        print(f"✓ Account: {account}")
        
        # Test orderbook
        orderbook = await client.get_order_book_details(settings.trading_market_id)
        print(f"✓ Orderbook retrieved")
        
        # Test funding
        funding = await client.get_funding_rates(settings.trading_market_id)
        print(f"✓ Funding: {funding}")
        
        print("\n✓✓✓ All tests passed! ✓✓✓\n")
        
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        import traceback
        traceback.print_exc()
    
    finally:
        await close_client()


if __name__ == "__main__":
    asyncio.run(test())
