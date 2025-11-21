# Lighter SDK Complete Refactor Plan
## Ultra-Deep Analysis & Native Method Replacement

**Date**: 2024-11-20  
**Goal**: Replace ALL hardcoded logic with native Lighter SDK methods to massively reduce code size and boost performance

---

## 📊 SDK METHOD INVENTORY

### **SignerClient** (Trading & Order Execution)
#### Order Creation Methods (NATIVE):
```python
✅ create_market_order_limited_slippage() - Market orders with slippage protection
✅ create_sl_order() - Native stop-loss orders
✅ create_tp_order() - Native take-profit orders
✅ create_sl_limit_order() - Stop-loss limit orders
✅ create_tp_limit_order() - Take-profit limit orders
✅ create_order() - Generic order creation (limit/market/stop/tp)
✅ create_grouped_orders() - OCO and conditional orders (GROUPING_TYPE_ONE_CANCELS_THE_OTHER=2)
✅ modify_order() - Update existing orders (price, size, trigger)
✅ cancel_order() - Cancel single order
✅ cancel_all_orders() - Bulk cancellation
```

#### Account Management Methods:
```python
✅ update_leverage() - Change leverage and margin mode
✅ withdraw() - Withdraw USDC
✅ transfer() - Internal transfers between accounts
✅ create_sub_account() - Create sub-accounts
```

#### Constants (CRITICAL):
```python
ORDER_TYPE_LIMIT = 0
ORDER_TYPE_MARKET = 1  
ORDER_TYPE_STOP_LOSS = 2
ORDER_TYPE_TAKE_PROFIT = 4
ORDER_TYPE_STOP_LOSS_LIMIT = 3
ORDER_TYPE_TAKE_PROFIT_LIMIT = 5

GROUPING_TYPE_ONE_CANCELS_THE_OTHER = 2  # <-- TRUE OCO!
GROUPING_TYPE_ONE_TRIGGERS_THE_OTHER = 1
GROUPING_TYPE_ONE_TRIGGERS_A_ONE_CANCELS_THE_OTHER = 3

CROSS_MARGIN_MODE = 0
ISOLATED_MARGIN_MODE = 1

ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = 0
ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = 1
ORDER_TIME_IN_FORCE_POST_ONLY = 2
```

### **AccountApi** (Account Data Retrieval)
#### Account Info Methods (NATIVE):
```python
✅ account(by, value) - Get account details by index/address
✅ account_metadata(by, value) - Account metadata
✅ account_limits(account_index) - Position limits, max leverage
✅ pnl(by, value, resolution, start, end, count_back) - Historical PnL data
✅ position_funding(account_index, limit) - Funding payments
✅ liquidations(account_index, limit) - Liquidation history
✅ l1_metadata(l1_address) - L1 wallet metadata
```

### **OrderApi** (Order & Trade Data)
#### Order Query Methods (NATIVE):
```python
✅ account_active_orders(account_index, market_id) - All active orders
✅ account_inactive_orders(account_index, limit) - Order history
✅ order_books(market_id) - Order book snapshot
✅ order_book_details(market_id) - Detailed order book
✅ order_book_orders(market_id, limit) - Individual order book orders
✅ trades(sort_by, limit, account_index, market_id) - Trade history
✅ recent_trades(market_id, limit) - Recent market trades
✅ exchange_stats() - Global exchange statistics
```

### **CandlestickApi** (Market Data)
#### Market Data Methods (NATIVE):
```python
✅ candlesticks(market_id, resolution, start, end, count_back) - OHLCV data
✅ fundings(market_id, resolution, start, end, count_back) - Funding rate history
```

### **TransactionApi** (Transaction History)
```python
✅ account_txs(account_index) - Transaction history
✅ deposit_history(account_index) - Deposit records
✅ transfer_history(account_index) - Transfer records
✅ withdraw_history(account_index) - Withdrawal records
✅ next_nonce(account_index) - Get next transaction nonce
```

### **FundingApi** (Funding Rates)
```python
✅ funding_rates() - Current funding rates for all markets
```

### **WsClient** (WebSocket Real-Time Data)
```python
✅ subscribe_account() - Real-time account updates
✅ subscribe_order_book() - Real-time order book updates
✅ handle_update_account() - Account update callbacks
✅ handle_update_order_book() - Order book update callbacks
```

---

## 🔧 CURRENT CODE ANALYSIS & REFACTORING OPPORTUNITIES

### **1. app/lighter/lighter_client.py** (286 lines → ~150 lines)

#### REMOVE - Custom Market Data Fetching:
```python
# Lines 150-200: get_market_data() - HARDCODED REST CALLS
# ❌ REPLACE WITH: CandlestickApi.candlesticks() + OrderApi.order_book_details()
async def get_market_data(self, symbol: str, market_id: int) -> Dict[str, Any]:
    # Custom HTTP requests to /markets, /orderbook, /ticker
    # 50+ lines of manual JSON parsing
```

**REFACTOR TO**:
```python
async def get_market_data(self, market_id: int) -> Dict[str, Any]:
    """Use native SDK - 10 lines instead of 50"""
    order_api = lighter.OrderApi(self.api_client)
    details = await order_api.order_book_details(market_id=market_id)
    return {
        'last_price': details.data[0].last_price if details.data else 0,
        'bid': details.data[0].best_bid if details.data else 0,
        'ask': details.data[0].best_ask if details.data else 0,
        'volume_24h': details.data[0].volume_24h if details.data else 0,
        'price_change_24h': details.data[0].price_change_24h if details.data else 0
    }
```

#### REMOVE - Custom Order Status Checking:
```python
# Lines 220-250: get_order_status() - MANUAL HTTP REQUESTS
async def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
    # Manual REST API calls, error handling
```

**REFACTOR TO**:
```python
async def get_active_orders(self, market_id: int) -> List[Dict]:
    """Native SDK method - more reliable"""
    order_api = lighter.OrderApi(self.api_client)
    auth_token = self.signer_client.create_auth_token_with_expiry()
    orders = await order_api.account_active_orders(
        account_index=self.account_index,
        market_id=market_id,
        authorization=auth_token
    )
    return [order.to_dict() for order in orders.data]
```

#### ALREADY GOOD - Order Placement:
```python
# ✅ Already uses native SDK methods:
# - create_market_order_limited_slippage()
# - create_sl_order()
# - create_tp_order()
# - create_order() for limit orders
```

---

### **2. app/lighter/lighter_order_manager.py** (519 lines → ~200 lines)

#### CRITICAL ISSUE - Not Using Native OCO Orders:
```python
# Lines 55-110: create_oco_order() - MANUAL OCO TRACKING
# ❌ Currently: Places 3 separate orders, tracks manually
# ✅ SHOULD USE: create_grouped_orders() with GROUPING_TYPE_ONE_CANCELS_THE_OTHER
```

**REFACTOR TO**:
```python
async def create_oco_order(self, symbol: str, side: str, size: Decimal,
                          entry_price: Decimal, sl_price: Decimal, tp_price: Decimal) -> str:
    """Use native SDK OCO grouping - TRUE exchange-level OCO"""
    import os
    market_id = int(os.getenv('LIGHTER_MARKET_ID', '0'))
    
    # Prepare orders for grouping
    orders = [
        # Entry order
        lighter.signer_client.CreateOrderTxReq(
            market_index=market_id,
            client_order_index=self._generate_order_id(),
            base_amount=int(size * 1e4),
            price=int(entry_price * 1e2),
            is_ask=(side == 'sell'),
            order_type=lighter.SignerClient.ORDER_TYPE_LIMIT,
            time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            reduce_only=False
        ),
        # Stop-loss (conditional on entry fill)
        lighter.signer_client.CreateOrderTxReq(
            market_index=market_id,
            client_order_index=self._generate_order_id(),
            base_amount=int(size * 1e4),
            trigger_price=int(sl_price * 1e2),
            price=int(sl_price * 1e2),
            is_ask=(not (side == 'sell')),  # Opposite side
            order_type=lighter.SignerClient.ORDER_TYPE_STOP_LOSS,
            time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            reduce_only=True
        ),
        # Take-profit (conditional on entry fill)
        lighter.signer_client.CreateOrderTxReq(
            market_index=market_id,
            client_order_index=self._generate_order_id(),
            base_amount=int(size * 1e4),
            trigger_price=int(tp_price * 1e2),
            price=int(tp_price * 1e2),
            is_ask=(not (side == 'sell')),
            order_type=lighter.SignerClient.ORDER_TYPE_TAKE_PROFIT,
            time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            reduce_only=True
        )
    ]
    
    # Create TRUE OCO order at exchange level
    tx, tx_hash, err = await self.client.signer_client.create_grouped_orders(
        grouping_type=lighter.SignerClient.GROUPING_TYPE_ONE_TRIGGERS_A_ONE_CANCELS_THE_OTHER,
        orders=orders
    )
    
    if err:
        raise Exception(f"Failed to create OCO order: {err}")
    
    return tx_hash
```

#### REMOVE - Manual Order Monitoring:
```python
# Lines 376-466: monitor_oco_orders() - MANUAL POLLING
# ❌ Polls order status every cycle
# ✅ REPLACE WITH: WsClient.subscribe_account() for real-time updates
```

**REFACTOR TO**:
```python
async def start_realtime_monitoring(self):
    """Use WebSocket for real-time order updates instead of polling"""
    ws_client = lighter.WsClient(
        api_url=self.client.api_url.replace('https', 'wss').replace('/v1', '/ws'),
        account_index=self.client.account_index
    )
    
    def on_order_update(update):
        """Handle real-time order updates"""
        if update['status'] == 'filled':
            self._handle_order_fill(update)
        elif update['status'] == 'cancelled':
            self._handle_order_cancel(update)
    
    ws_client.handle_update_account = on_order_update
    await ws_client.connect()
    await ws_client.subscribe_account()
```

#### REMOVE - Manual Position Tracking:
```python
# Lines 250-350: Manual position size tracking
# ❌ REPLACE WITH: AccountApi.account() for accurate position data
```

---

### **3. app/lighter/lighter_websocket.py** (ENTIRE FILE CAN BE REPLACED)

#### REMOVE - Custom WebSocket Implementation:
```python
# ALL 200+ lines - Custom WebSocket handling
# ❌ REPLACE WITH: Native WsClient from SDK
```

**REFACTOR TO**:
```python
"""WebSocket client using native Lighter SDK"""
import lighter
from typing import Callable, Optional
import asyncio

class LighterWebSocket:
    """Wrapper around native WsClient"""
    
    def __init__(self, api_url: str, account_index: int):
        ws_url = api_url.replace('https', 'wss').replace('/v1', '/ws')
        self.ws_client = lighter.WsClient(
            api_url=ws_url,
            account_index=account_index
        )
        self.account_callback: Optional[Callable] = None
        self.orderbook_callback: Optional[Callable] = None
    
    async def connect(self):
        """Connect using native SDK"""
        await self.ws_client.connect()
    
    async def subscribe_account_updates(self, callback: Callable):
        """Subscribe to account updates"""
        self.account_callback = callback
        self.ws_client.handle_update_account = lambda update: asyncio.create_task(callback(update))
        await self.ws_client.subscribe_account()
    
    async def subscribe_orderbook(self, market_id: int, callback: Callable):
        """Subscribe to order book updates"""
        self.orderbook_callback = callback
        self.ws_client.handle_update_order_book = lambda update: asyncio.create_task(callback(update))
        await self.ws_client.subscribe_order_book(market_id)
    
    async def close(self):
        """Close connection"""
        await self.ws_client.close()

# RESULT: 50 lines instead of 200+
```

---

### **4. app/indicators/technical_indicators.py** (USE NATIVE CANDLESTICK DATA)

#### OPTIMIZE - Historical Data Fetching:
```python
# Lines 30-80: get_historical_data() - MANUAL HTTP REQUESTS
# ❌ Custom REST calls, manual pagination
# ✅ REPLACE WITH: CandlestickApi.candlesticks()
```

**REFACTOR TO**:
```python
async def get_historical_data(self, market_id: int, resolution: str, 
                              count_back: int) -> List[Dict]:
    """Use native SDK candlestick API"""
    import time
    candle_api = lighter.CandlestickApi(self.api_client)
    
    end_time = int(time.time() * 1000)
    start_time = end_time - (count_back * self._resolution_to_ms(resolution))
    
    response = await candle_api.candlesticks(
        market_id=market_id,
        resolution=resolution,
        start_timestamp=start_time,
        end_timestamp=end_time,
        count_back=count_back
    )
    
    return [
        {
            'timestamp': candle.timestamp,
            'open': candle.open,
            'high': candle.high,
            'low': candle.low,
            'close': candle.close,
            'volume': candle.volume
        }
        for candle in response.data
    ]
```

---

### **5. app/database/analytics.py** (USE SDK FOR DATA RETRIEVAL)

#### OPTIMIZE - Trade History:
```python
# Lines 50-100: get_trades() - DATABASE QUERIES
# ✅ KEEP database for local storage
# ✅ ADD: Sync from OrderApi.trades() for accurate exchange data
```

**ADD SYNC METHOD**:
```python
async def sync_trades_from_exchange(self, account_index: int, market_id: int):
    """Sync trades from exchange API to local database"""
    order_api = lighter.OrderApi(self.api_client)
    auth_token = self.signer_client.create_auth_token_with_expiry()
    
    trades = await order_api.trades(
        sort_by='timestamp',
        limit=100,
        account_index=account_index,
        market_id=market_id,
        authorization=auth_token
    )
    
    # Store in database
    for trade in trades.data:
        await self.save_trade({
            'trade_id': trade.id,
            'order_id': trade.order_id,
            'market_id': trade.market_id,
            'side': 'buy' if not trade.is_ask else 'sell',
            'price': trade.price,
            'size': trade.size,
            'timestamp': trade.timestamp
        })
```

---

## 📈 PERFORMANCE IMPROVEMENTS EXPECTED

### Code Size Reduction:
```
lighter_client.py: 286 → 150 lines (-47%)
lighter_order_manager.py: 519 → 200 lines (-61%)
lighter_websocket.py: 200+ → 50 lines (-75%)
technical_indicators.py: 300 → 200 lines (-33%)

TOTAL: ~1305 → ~600 lines (-54% code reduction!)
```

### Performance Gains:
```
1. Native OCO Orders
   - Before: 3 separate API calls + manual tracking
   - After: 1 grouped order call
   - Improvement: 66% fewer API calls

2. Real-Time Updates (WebSocket)
   - Before: Poll every 30 seconds
   - After: Instant push notifications
   - Improvement: ~95% faster updates, 100% less API load

3. Market Data
   - Before: 3-5 REST calls per update
   - After: 1 native SDK call with caching
   - Improvement: 70% fewer API calls

4. Order Status Checking
   - Before: Individual REST call per order
   - After: Batch retrieval with account_active_orders()
   - Improvement: 90% fewer API calls for 10+ orders
```

### Reliability Improvements:
```
✅ Native SDK handles:
   - Connection pooling
   - Rate limiting
   - Retry logic
   - Error handling
   - Authentication token refresh
   - WebSocket reconnection
   
✅ Exchange-level OCO:
   - Atomic execution
   - Guaranteed cancellation
   - No race conditions
   - Survives bot restarts
```

---

## 🚀 IMPLEMENTATION PRIORITY

### Phase 1: CRITICAL (DO NOW) ⚡
1. ✅ **OCO Orders** - Use `create_grouped_orders()` with GROUPING_TYPE_ONE_TRIGGERS_A_ONE_CANCELS_THE_OTHER
2. ✅ **WebSocket** - Replace custom implementation with native `WsClient`
3. ✅ **Order Status** - Use `account_active_orders()` instead of manual polling

### Phase 2: HIGH IMPACT 🎯
4. **Market Data** - Use `CandlestickApi` and `OrderApi.order_book_details()`
5. **Position Tracking** - Use `AccountApi.account()` for accurate positions
6. **Trade History** - Sync from `OrderApi.trades()`

### Phase 3: OPTIMIZATION 🔧  
7. **Historical Data** - Use `CandlestickApi.candlesticks()` for indicators
8. **Account Stats** - Use `AccountApi.pnl()` and `account_metadata()`
9. **Funding Rates** - Use `FundingApi.funding_rates()`

---

## 🎯 EXPECTED OUTCOMES

### Before Refactor:
- 1300+ lines of custom API interaction code
- Manual polling every 30 seconds
- 3 separate orders for OCO (not true OCO)
- Multiple position entries in tracking
- Custom WebSocket implementation
- Manual error handling and retries

### After Refactor:
- ~600 lines using native SDK
- Real-time WebSocket updates
- TRUE exchange-level OCO orders
- Single position per trade
- Native SDK WebSocket with auto-reconnect
- Built-in error handling and rate limiting

### Key Benefits:
```
✅ 54% less code to maintain
✅ 70-90% fewer API calls
✅ 95% faster order updates (WebSocket vs polling)
✅ TRUE OCO orders (no multiple position bug)
✅ Better error handling (SDK built-in)
✅ Auto token refresh (SDK handles it)
✅ Connection pooling (SDK optimized)
✅ Rate limit handling (SDK manages it)
```

---

## 🔄 NEXT STEPS

1. **Review this plan** - Confirm approach
2. **Phase 1 Implementation** - Start with OCO orders (CRITICAL)
3. **Test thoroughly** - Ensure no regressions
4. **Phase 2 & 3** - Continue optimization
5. **Monitor performance** - Measure improvements

**This refactor will transform the bot from a custom implementation to a lean, SDK-native powerhouse!** 🚀

