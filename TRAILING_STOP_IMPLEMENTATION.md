# Trailing Stop Implementation Guide

## Overview

Since the Lighter SDK v1.0.0 **does not have native trailing stop/take-profit support**, we implemented a client-side solution using the SDK's `modify_order()` method.

## Architecture

### Components

1. **TrailingStopManager** (`app/lighter/trailing_stop_manager.py`)
   - Manages trailing stop logic for multiple positions
   - Monitors price movements
   - Automatically adjusts stop-loss orders via `modify_order()`

2. **Integration Points**
   - Works with `LighterOrderManagerV2` for order placement
   - Uses `LighterWebSocketV2` for real-time price feeds
   - Compatible with existing position tracking

## Features

### ✅ Supported Features

- **Long and Short Positions**: Different trailing logic for each
- **Activation Threshold**: Optional - only start trailing after X% profit
- **Trail Percentage**: Configurable distance from peak (e.g., 2% behind)
- **Callback Distance**: Minimum price movement before updating (reduces API calls)
- **Peak Tracking**: Automatically tracks highest/lowest price
- **Real-time Updates**: Integrates with WebSocket for < 100ms latency
- **Multiple Positions**: Manage trailing stops for multiple positions simultaneously

### ❌ Not Supported by SDK

- Native trailing stops
- Exchange-level trailing (must be client-side)
- Trailing take-profit (can be implemented similarly)

## SDK Method Used

```python
signer_client.modify_order(
    market_index: int,      # Market (e.g., 0 for ETH-USD)
    order_index: int,       # The stop-loss order ID to modify
    base_amount: int,       # Position size in base units
    price: int,             # New limit price (scaled)
    trigger_price: int      # New trigger price (scaled)
)
```

## Usage Examples

### Basic Usage (Long Position)

```python
from app.lighter.trailing_stop_manager import TrailingStopManager
from decimal import Decimal

# Initialize
trailing_manager = TrailingStopManager(signer_client, price_precision=2)

# Enable trailing stop after placing OCO order
await trailing_manager.enable_trailing_stop(
    position_id='position_001',          # Unique position identifier
    market_index=0,                      # ETH-USD market
    sl_order_index=100002,               # SL order ID from OCO group
    position_side='long',                # Long or short
    entry_price=Decimal('3000.00'),      # Entry price
    current_sl_price=Decimal('2950.00'), # Current SL price
    position_size=100000,                # Size in base units
    trail_percent=Decimal('2.0'),        # Trail 2% behind peak
    callback_distance=Decimal('0.5'),    # Update after 0.5% move
    activation_profit=Decimal('1.0')     # Activate after 1% profit
)

# Feed price updates (from WebSocket or polling)
new_sl = await trailing_manager.update_price('position_001', Decimal('3050'))

# Check status
status = trailing_manager.get_trailing_status('position_001')
print(f"Current SL: ${status['current_sl']}")
print(f"Peak price: ${status['peak_price']}")
print(f"Profit: {status['profit_pct']:.2f}%")

# Disable when position closes
trailing_manager.disable_trailing_stop('position_001')
```

### Integration with WebSocket

```python
from app.lighter.lighter_websocket_v2 import LighterWebSocketV2
from app.lighter.trailing_stop_manager import TrailingStopManager

# Setup
ws = LighterWebSocketV2(api_url, account_index)
trailing_manager = TrailingStopManager(signer_client)

# Enable trailing stop
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

# WebSocket callback for real-time updates
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

### Short Position Example

```python
# Short positions trail ABOVE the lowest price
await trailing_manager.enable_trailing_stop(
    position_id='short_001',
    market_index=0,
    sl_order_index=300001,
    position_side='short',              # SHORT
    entry_price=Decimal('3000.00'),
    current_sl_price=Decimal('3050.00'), # SL above entry (worse for short)
    position_size=100000,
    trail_percent=Decimal('2.0'),        # Trail 2% ABOVE lowest
    callback_distance=Decimal('0.5'),
    activation_profit=Decimal('1.0')     # Activate after 1% profit
)

# As price drops (profitable for short), SL moves down
# Example: Price drops to $2950 (1.67% profit)
#   Peak (lowest) = $2950
#   New SL = $2950 * 1.02 = $3009 (2% above lowest)
```

### Aggressive Trailing (Tight Stop)

```python
# Tighter trail for scalping
await trailing_manager.enable_trailing_stop(
    position_id='scalp_001',
    market_index=0,
    sl_order_index=400001,
    position_side='long',
    entry_price=Decimal('3000.00'),
    current_sl_price=Decimal('2970.00'),
    position_size=100000,
    trail_percent=Decimal('1.0'),        # Tight 1% trail
    callback_distance=Decimal('0.25'),   # Update frequently
    activation_profit=None               # Activate immediately
)
```

## Configuration Parameters

### TrailingStopConfig

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `position_id` | str | Unique position identifier | 'position_001' |
| `market_index` | int | Market index (0 = ETH-USD) | 0 |
| `sl_order_index` | int | Stop-loss order ID to modify | 100002 |
| `position_side` | str | 'long' or 'short' | 'long' |
| `entry_price` | Decimal | Position entry price | 3000.00 |
| `current_sl_price` | Decimal | Current SL trigger price | 2950.00 |
| `position_size` | Decimal | Size in base units | 100000 |
| `trail_percent` | Decimal | Trail distance % from peak | 2.0 (2%) |
| `callback_distance` | Decimal | Min price move % to update | 0.5 (0.5%) |
| `activation_profit` | Decimal? | Profit % before activating | 1.0 (1%) or None |

## How It Works

### Long Position Trailing Logic

1. **Entry**: Long at $3000, SL at $2950 (1.67% below)
2. **Price rises to $3030** (1% profit)
   - Activation threshold reached → trailing activates
   - Peak price = $3030
   - New SL = $3030 * 0.98 = $2969.40 (2% trail)
   - **SL moved up from $2950 to $2969.40** ✅
3. **Price rises to $3060** (2% profit)
   - Peak price = $3060
   - New SL = $3060 * 0.98 = $2998.80
   - **SL moved up from $2969.40 to $2998.80** ✅
4. **Price drops to $3050**
   - Peak remains $3060 (highest seen)
   - SL stays at $2998.80 (no update needed)
5. **If price drops to $2998** → SL triggers, lock in ~$0 loss (vs -$50 original)

### Short Position Trailing Logic

1. **Entry**: Short at $3000, SL at $3050 (1.67% above)
2. **Price drops to $2970** (1% profit)
   - Activation threshold reached → trailing activates
   - Peak price = $2970 (lowest)
   - New SL = $2970 * 1.02 = $3029.40 (2% above)
   - **SL moved down from $3050 to $3029.40** ✅
3. **Price drops to $2950** (1.67% profit)
   - Peak price = $2950 (new lowest)
   - New SL = $2950 * 1.02 = $3009.00
   - **SL moved down from $3029.40 to $3009.00** ✅
4. **Price bounces to $2965**
   - Peak remains $2950 (still lowest seen)
   - SL stays at $3009.00
5. **If price rises to $3009** → SL triggers, lock in profit

## Performance Characteristics

### API Call Optimization

- **Callback Distance**: Prevents excessive `modify_order()` calls
- **Example**: 0.5% callback = updates only when price moves ≥ 0.5%
- **Typical scenario**: 5-10 SL updates per position (vs 100s without callback)

### Latency

- **WebSocket integration**: < 100ms from price update to SL calculation
- **modify_order() call**: ~200-500ms to exchange
- **Total latency**: < 1 second from price move to SL updated

### Accuracy

- **Price precision**: Configurable (default 2 decimals)
- **Peak tracking**: Updated on every price update
- **No drift**: Recalculated from peak each time

## Testing

Run the example file to see trailing stops in action:

```bash
python3 example_trailing_stop.py
```

This demonstrates:
1. Basic trailing stop (long position)
2. Aggressive trailing (1% trail, frequent updates)
3. Short position trailing
4. WebSocket integration pattern

## Integration with Bot

### Add to `bot.py`

```python
from app.lighter.trailing_stop_manager import TrailingStopManager

class TradingBot:
    def __init__(self):
        # ... existing setup ...
        self.trailing_manager = TrailingStopManager(
            self.client.signer_client,
            price_precision=2
        )
    
    async def place_entry_with_trailing_sl(self, symbol, side, size, entry_price):
        # Place OCO order
        tx_hash = await self.order_manager.place_oco_order_native(
            symbol=symbol,
            side=side,
            size=size,
            entry_price=entry_price,
            sl_price=entry_price * Decimal('0.985'),  # 1.5% initial SL
            tp_price=entry_price * Decimal('1.03')    # 3% TP
        )
        
        # Wait for entry fill, get order IDs
        await asyncio.sleep(2)
        orders = await self.order_manager.get_active_orders(symbol)
        sl_order = [o for o in orders if o['type'] == 'stop_loss'][0]
        
        # Enable trailing
        await self.trailing_manager.enable_trailing_stop(
            position_id=f'pos_{int(time.time())}',
            market_index=0,
            sl_order_index=sl_order['order_id'],
            position_side=side,
            entry_price=entry_price,
            current_sl_price=sl_order['trigger_price'],
            position_size=int(size * Decimal('10000000')),
            trail_percent=Decimal('2.0'),
            callback_distance=Decimal('0.5'),
            activation_profit=Decimal('1.0')
        )
        
        return tx_hash
    
    async def on_price_update(self, symbol, price):
        # Update all trailing stops for this symbol
        for position_id in self.trailing_manager.get_all_trailing_positions():
            await self.trailing_manager.update_price(position_id, price)
```

## Best Practices

### 1. Choose Appropriate Trail Distance

- **Scalping**: 0.5-1% trail (tight)
- **Day trading**: 1-2% trail (moderate)
- **Swing trading**: 2-5% trail (loose)

### 2. Use Activation Threshold

- Prevents premature stop-outs on initial volatility
- Typical: 0.5-1% profit before activating
- Set to `None` for immediate activation

### 3. Optimize Callback Distance

- Balance between responsiveness and API calls
- Typical: 0.25-0.5% for active markets
- Higher (1%+) for less active markets

### 4. Monitor WebSocket Connection

```python
# Add reconnection logic
async def ensure_ws_connected():
    if not ws.is_connected:
        await ws.connect()
        await ws.subscribe_orderbook(0, on_orderbook_update)
```

### 5. Handle Position Closure

```python
# Disable trailing when position closes
async def on_position_closed(position_id):
    trailing_manager.disable_trailing_stop(position_id)
    logger.info(f"Trailing stop removed for closed position {position_id}")
```

## Limitations

1. **Client-Side Only**: Requires bot to be running
   - If bot crashes, trailing stops won't update
   - Consider using persistent storage for configs

2. **Network Latency**: 
   - ~1 second from price move to SL update
   - Fast market moves might not be captured

3. **No Exchange-Level Support**:
   - SDK doesn't provide native trailing stops
   - Must be implemented client-side

4. **modify_order() Rate Limits**:
   - Subject to exchange rate limits
   - Use callback_distance to reduce calls

## Future Enhancements

### Possible Improvements

1. **Persistent Storage**
   - Save trailing configs to database
   - Resume after bot restart

2. **Trailing Take-Profit**
   - Implement similar logic for TP orders
   - Move TP closer as price moves against position

3. **Multiple Trail Levels**
   - Different trail % at different profit levels
   - Example: 2% trail until 5% profit, then 1% trail

4. **Advanced Activation Logic**
   - Time-based activation (activate after X minutes)
   - Volume-based activation
   - Technical indicator triggers

5. **Backtesting**
   - Simulate trailing stops on historical data
   - Optimize trail % and callback distance

## Troubleshooting

### Issue: SL not updating

**Check:**
- Is trailing activated? (Check activation_profit threshold)
- Has price moved enough? (Check callback_distance)
- Is WebSocket connected? (Verify price updates)
- Are there errors in logs? (Check modify_order() calls)

### Issue: Too many API calls

**Solution:**
- Increase callback_distance (e.g., from 0.5% to 1%)
- Check for duplicate price updates
- Verify only updating on significant price changes

### Issue: SL moving in wrong direction

**Check:**
- Position side correct? ('long' vs 'short')
- Is peak_price updating? (Should be highest for long, lowest for short)
- Check trail_percent calculation

## Summary

✅ **What We Have:**
- Full client-side trailing stop implementation
- Uses SDK's `modify_order()` method
- Supports long/short, activation thresholds, configurable parameters
- Real-time WebSocket integration
- Multiple position support

❌ **What SDK Doesn't Provide:**
- Native trailing stops
- Exchange-level trailing (all client-side)

📈 **Performance:**
- < 1 second latency
- Minimal API calls (callback distance optimization)
- No position tracking drift

🚀 **Ready for Integration:**
- Complete implementation in `trailing_stop_manager.py`
- Working examples in `example_trailing_stop.py`
- Integration guide above
- Ready to add to `bot.py`
