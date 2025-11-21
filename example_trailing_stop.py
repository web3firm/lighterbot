"""
Example: Using Trailing Stop Manager with Lighter SDK

This demonstrates how to use the client-side trailing stop implementation
since the SDK doesn't have native trailing stop support.
"""

import asyncio
from decimal import Decimal
from app.lighter.trailing_stop_manager import TrailingStopManager
# from app.lighter.lighter_order_manager_v2 import LighterOrderManagerV2
# from app.lighter.lighter_client import LighterClient
# from config.credentials import LIGHTER_API_KEY, LIGHTER_API_SECRET


async def example_1_basic_trailing_stop():
    """
    Example 1: Basic trailing stop
    - Enter long position with OCO (entry + SL + TP)
    - Enable trailing stop on the SL order
    - Simulate price movements and watch SL adjust
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Basic Trailing Stop")
    print("=" * 80)
    
    # Mock setup for demonstration
    from unittest.mock import Mock
    mock_signer = Mock()
    trailing_manager = TrailingStopManager(mock_signer, price_precision=2)
    
    # Step 1: Place OCO order (Entry + SL + TP)
    print("\n📊 Simulating OCO order placement...")
    
    symbol = 'ETH-USD'
    entry_price = Decimal('3000.00')
    sl_price = Decimal('2950.00')  # 1.67% below entry
    tp_price = Decimal('3100.00')  # 3.33% above entry
    size = Decimal('0.01')  # 0.01 ETH
    
    print(f"✅ OCO order: Entry=${entry_price}, SL=${sl_price}, TP=${tp_price}")
    
    # Assume entry fills and we get the order IDs
    position_id = 'position_001'
    sl_order_index = 100002  # The SL order from the OCO group
    position_size = int(size * Decimal('10000000'))  # Convert to base units
    
    # Step 2: Enable trailing stop
    print("\n🔄 Enabling trailing stop...")
    
    await trailing_manager.enable_trailing_stop(
        position_id=position_id,
        market_index=0,  # ETH-USD
        sl_order_index=sl_order_index,
        position_side='long',
        entry_price=entry_price,
        current_sl_price=sl_price,
        position_size=position_size,
        trail_percent=Decimal('2.0'),  # Trail 2% behind peak
        callback_distance=Decimal('0.5'),  # Update after 0.5% move
        activation_profit=Decimal('1.0')  # Activate after 1% profit
    )
    
    print("✅ Trailing stop enabled")
    print(f"   Trail: 2% behind peak")
    print(f"   Callback: 0.5% movement")
    print(f"   Activation: After 1% profit")
    
    # Step 3: Simulate price movements
    print("\n📈 Simulating price movements...")
    
    price_scenarios = [
        (Decimal('3005'), "Small move up (+0.17%)"),
        (Decimal('3015'), "Breaking activation threshold (+0.5%)"),
        (Decimal('3030'), "Profit reached, trailing activates (+1.0%)"),
        (Decimal('3045'), "Further profit (+1.5%)"),
        (Decimal('3060'), "Peak price (+2.0%)"),
        (Decimal('3055'), "Small pullback"),
        (Decimal('3070'), "New peak (+2.3%)"),
        (Decimal('3050'), "Larger pullback (-0.65%)"),
    ]
    
    for price, description in price_scenarios:
        print(f"\n💰 Price: ${price} - {description}")
        
        new_sl = await trailing_manager.update_price(position_id, price)
        
        if new_sl:
            print(f"   ✅ Stop-loss updated to: ${new_sl}")
        else:
            print(f"   ⏸️  No update needed")
        
        # Show current status
        status = trailing_manager.get_trailing_status(position_id)
        if status:
            print(f"   Current SL: ${status['current_sl']:.2f}")
            print(f"   Peak: ${status['peak_price']:.2f}")
            print(f"   Profit: {status['profit_pct']:.2f}%")
            print(f"   Activated: {status['activated']}")
        
        await asyncio.sleep(0.5)
    
    # Step 4: Disable trailing stop
    print("\n\n🛑 Disabling trailing stop...")
    trailing_manager.disable_trailing_stop(position_id)
    print("✅ Trailing stop disabled")


async def example_2_aggressive_trailing():
    """
    Example 2: Aggressive trailing (tight stop)
    - Tighter trail distance (1%)
    - No activation threshold (immediate)
    - Quick callback (0.25%)
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Aggressive Trailing Stop")
    print("=" * 80)
    
    # Setup (simplified)
    from unittest.mock import Mock
    
    mock_signer = Mock()
    trailing_manager = TrailingStopManager(mock_signer, price_precision=2)
    
    # Enable aggressive trailing
    await trailing_manager.enable_trailing_stop(
        position_id='aggressive_001',
        market_index=0,
        sl_order_index=200001,
        position_side='long',
        entry_price=Decimal('3000.00'),
        current_sl_price=Decimal('2970.00'),  # 1% below
        position_size=100000,
        trail_percent=Decimal('1.0'),  # Tight 1% trail
        callback_distance=Decimal('0.25'),  # Quick updates
        activation_profit=None  # Immediate activation
    )
    
    print("✅ Aggressive trailing enabled (1% trail, 0.25% callback, immediate)")
    
    # Simulate price action
    prices = [
        Decimal('3010'), Decimal('3020'), Decimal('3030'),
        Decimal('3025'), Decimal('3035'), Decimal('3028')
    ]
    
    print("\n📈 Price movements:")
    for price in prices:
        new_sl = await trailing_manager.update_price('aggressive_001', price)
        status = trailing_manager.get_trailing_status('aggressive_001')
        
        print(f"   Price: ${price} | SL: ${status['current_sl']:.2f} | Peak: ${status['peak_price']:.2f}")


async def example_3_short_position_trailing():
    """
    Example 3: Trailing stop for SHORT position
    - Logic is inverted (SL trails above lowest price)
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Trailing Stop for Short Position")
    print("=" * 80)
    
    from unittest.mock import Mock
    
    mock_signer = Mock()
    trailing_manager = TrailingStopManager(mock_signer, price_precision=2)
    
    # Short position: entered at $3000, SL at $3050 (above)
    await trailing_manager.enable_trailing_stop(
        position_id='short_001',
        market_index=0,
        sl_order_index=300001,
        position_side='short',
        entry_price=Decimal('3000.00'),
        current_sl_price=Decimal('3050.00'),  # 1.67% above (worse for short)
        position_size=100000,
        trail_percent=Decimal('2.0'),  # Trail 2% above lowest
        callback_distance=Decimal('0.5'),
        activation_profit=Decimal('1.0')  # Activate after 1% profit
    )
    
    print("✅ Short position trailing enabled")
    print("   Entry: $3000")
    print("   Initial SL: $3050 (1.67% above)")
    print("   Trail: 2% above lowest price")
    
    # Simulate price dropping (profit for short)
    price_scenarios = [
        (Decimal('2995'), "Small drop"),
        (Decimal('2985'), "More profit"),
        (Decimal('2970'), "Activation threshold reached (-1%)"),
        (Decimal('2960'), "Further profit"),
        (Decimal('2950'), "Lowest point (-1.67% profit)"),
        (Decimal('2965'), "Bounce up"),
    ]
    
    print("\n📉 Price movements (short position):")
    for price, description in price_scenarios:
        new_sl = await trailing_manager.update_price('short_001', price)
        status = trailing_manager.get_trailing_status('short_001')
        
        print(f"\n   Price: ${price} - {description}")
        print(f"   SL: ${status['current_sl']:.2f} | Lowest: ${status['peak_price']:.2f}")
        print(f"   Profit: {status['profit_pct']:.2f}%")
        if new_sl:
            print(f"   ✅ SL updated to ${new_sl}")


async def example_4_integration_with_websocket():
    """
    Example 4: Real-time trailing with WebSocket price feed
    - Use WebSocket for live price updates
    - Automatic SL adjustment
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Integration with WebSocket")
    print("=" * 80)
    
    print("""
    Integration pattern with WebSocket:
    
    ```python
    from app.lighter.lighter_websocket_v2 import LighterWebSocketV2
    from app.lighter.trailing_stop_manager import TrailingStopManager
    
    # Setup
    ws = LighterWebSocketV2(api_url, account_index)
    trailing_manager = TrailingStopManager(signer_client)
    
    # Enable trailing for position
    await trailing_manager.enable_trailing_stop(
        position_id='pos_001',
        market_index=0,
        sl_order_index=sl_order_id,
        position_side='long',
        entry_price=Decimal('3000'),
        current_sl_price=Decimal('2950'),
        position_size=100000,
        trail_percent=Decimal('2.0'),
        callback_distance=Decimal('0.5')
    )
    
    # WebSocket callback
    async def on_orderbook_update(data):
        if 'best_bid' in data and 'best_ask' in data:
            mid_price = (data['best_bid'] + data['best_ask']) / 2
            
            # Update trailing stop with live price
            new_sl = await trailing_manager.update_price('pos_001', mid_price)
            
            if new_sl:
                print(f"🔄 Trailing SL updated to ${new_sl}")
    
    # Subscribe to orderbook
    await ws.connect()
    await ws.subscribe_orderbook(0, on_orderbook_update)
    ```
    
    This gives you:
    - Real-time price updates (< 100ms latency)
    - Automatic SL trailing
    - No polling needed
    """)


async def main():
    """Run all examples"""
    print("\n" + "=" * 80)
    print("TRAILING STOP MANAGER - EXAMPLES")
    print("=" * 80)
    print("\nSince Lighter SDK has no native trailing stops,")
    print("we implement it client-side using modify_order()")
    
    try:
        # Run examples
        await example_1_basic_trailing_stop()
        await example_2_aggressive_trailing()
        await example_3_short_position_trailing()
        await example_4_integration_with_websocket()
        
        print("\n" + "=" * 80)
        print("✅ ALL EXAMPLES COMPLETED")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
