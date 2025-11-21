# LighterBot Architecture

## System Design & Technical Overview

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Module Details](#module-details)
6. [Design Patterns](#design-patterns)
7. [Performance Characteristics](#performance-characteristics)
8. [Security Architecture](#security-architecture)

---

## System Overview

LighterBot is an institutional-grade algorithmic trading system built on the Lighter Protocol decentralized exchange. The system employs a modular architecture with clear separation of concerns, enabling high-performance automated trading with comprehensive risk management.

### Key Features
- **Native SDK Integration**: Direct use of Lighter SDK for optimal performance
- **Real-Time Processing**: WebSocket-based event streaming (<100ms latency)
- **Advanced Risk Management**: Multi-layered protection with kill switch
- **Modular Design**: Pluggable strategies, indicators, and risk modules
- **Enterprise Reliability**: Comprehensive error handling and recovery
- **Production Ready**: Tested with real funds on testnet

### Technology Stack
- **Language**: Python 3.9+
- **Protocol**: Lighter Protocol v1.0.0 SDK
- **Communication**: REST API + WebSocket
- **Database**: PostgreSQL (optional)
- **Notifications**: Telegram Bot API
- **ML Framework**: scikit-learn (optional)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LighterBot System                             │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │      Main Bot Loop        │
                    │   (1-second interval)     │
                    └─────────────┬─────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│  Market Data  │       │   Strategy    │       │     Risk      │
│    Module     │──────▶│   Manager     │──────▶│   Manager     │
└───────┬───────┘       └───────┬───────┘       └───────┬───────┘
        │                       │                       │
        │ ┌─────────────────────┤                       │
        │ │                     │                       │
        ▼ ▼                     ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│    Lighter    │       │     Order     │       │  Kill Switch  │
│ API Client    │       │   Manager     │       │  & Drawdown   │
└───────┬───────┘       └───────┬───────┘       └───────────────┘
        │                       │
        │                       │
        ├───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│   WebSocket   │       │   Trailing    │       │   Database    │
│   Real-Time   │       │     Stop      │       │   Manager     │
└───────────────┘       └───────────────┘       └───────────────┘
        │                       │                       │
        └───────────────────────┴───────────────────────┘
                                │
                                ▼
                        ┌───────────────┐
                        │   Telegram    │
                        │      Bot      │
                        └───────────────┘
```

---

## Core Components

### 1. Main Bot Controller (`app/bot.py`)
**Purpose**: Orchestrates all system components and manages the main trading loop

**Responsibilities**:
- Initialize and coordinate all modules
- Execute 1-second main loop
- Handle signals and graceful shutdown
- Manage bot state and statistics
- Coordinate between components

**Key Methods**:
- `initialize()`: Setup all components
- `run()`: Main trading loop
- `_check_and_execute_trade()`: Trade execution logic
- `_monitor_position()`: Position management
- `shutdown()`: Clean shutdown

### 2. Lighter Client (`app/lighter/lighter_client.py`)
**Purpose**: Low-level interface to Lighter Protocol

**Responsibilities**:
- Manage API client and signer
- Handle authentication
- Provide account state
- Coordinate protocol access

**Integration**:
```python
client = LighterClient(
    api_url="https://mainnet.zklighter.elliot.ai",
    api_private_key=os.getenv('LIGHTER_API_PRIVATE_KEY'),
    api_key_index=0,
    account_index=0
)
await client.connect()
```

### 3. Order Manager (`app/lighter/lighter_order_manager.py`)
**Purpose**: Execute orders using native SDK grouped orders (OCO)

**Key Innovation**: Native SDK OCO Implementation
- Single API call places entry + SL + TP atomically
- Exchange manages order relationships
- Zero position duplication risk
- 67% reduction in API calls vs manual approach

**Core Method**:
```python
async def place_oco_order_native(
    symbol: str, side: str, size: Decimal,
    entry_price: Decimal, sl_price: Decimal, tp_price: Decimal
) -> Optional[str]:
    # Creates grouped orders (Type 3: OCO)
    # Returns transaction hash
```

**Critical Parameters** (discovered through live testing):
- `ClientOrderIndex = 0` (SDK auto-generates IDs)
- `BaseAmount = 0` for SL/TP (inherit from entry)
- `TimeInForce = IOC` for stop orders (not GTT)

### 4. Market Data Module (`app/lighter/market_data.py`)
**Purpose**: Efficient market data retrieval using native SDK APIs

**Data Sources**:
- `CandlestickApi`: OHLCV data for indicators
- `OrderApi`: Order book and ticker data
- `FundingApi`: Funding rates and market stats

**Performance**:
- Smart caching (5-second TTL)
- Batch requests where possible
- 70% fewer API calls than manual REST

**Usage**:
```python
market_data = MarketData(api_client)
snapshot = await market_data.get_market_snapshot(market_id=0)
candles = await market_data.get_candlesticks(market_id=0, resolution='5m')
```

### 5. WebSocket Handler (`app/lighter/lighter_websocket.py`)
**Purpose**: Real-time updates using native SDK WsClient

**Features**:
- Account updates (order fills, cancellations)
- Order book updates (price changes)
- Automatic reconnection
- Event-driven callbacks

**Latency Improvement**:
- Polling approach: ~5 seconds
- WebSocket approach: <100ms
- 98% latency reduction

**Integration**:
```python
ws = LighterWebSocket(api_url, account_index)
await ws.connect()
await ws.subscribe_account(callback_function)
await ws.subscribe_orderbook(market_id, callback_function)
```

### 6. Trailing Stop Manager (`app/lighter/trailing_stop_manager.py`)
**Purpose**: Client-side trailing stops (SDK has no native support)

**Implementation**:
- Monitors price in real-time
- Calculates optimal stop-loss adjustment
- Uses SDK's `modify_order()` to update SL
- Configurable trail distance and activation

**Algorithm**:
```python
# For long positions:
if current_price > peak_price:
    peak_price = current_price
    new_sl = peak_price * (1 - trail_percent)
    if new_sl > current_sl:
        modify_order(new_sl)

# Inverted logic for short positions
```

### 7. Strategy Manager (`app/strategies/strategy_manager.py`)
**Purpose**: Signal generation and strategy coordination

**Strategy Types**:
- **Rule-Based**: Technical indicator strategies
  - Scalping (2% target)
  - Swing trading (longer timeframes)
- **ML-Based**: Machine learning predictions
  - XGBoost classifier
  - Feature engineering from indicators

**Signal Flow**:
```
Market Data → Technical Indicators → Strategy Logic → Signal
      ↓
Risk Validation → Position Sizing → Order Execution
```

### 8. Risk Manager (`app/risk/risk_manager.py`)
**Purpose**: Multi-layered risk protection

**Components**:

#### a) Kill Switch (`app/risk/kill_switch.py`)
- Monitors drawdown from session start
- Triggers at configurable threshold (default: 10%)
- Stops all trading until manual reset
- **Critical Fix**: Uses `collateral` not `available_balance`

#### b) Drawdown Monitor (`app/risk/drawdown_monitor.py`)
- Tracks peak equity and current drawdown
- Warns at warning threshold
- Triggers kill switch at critical threshold

#### c) Risk Engine (`app/risk/risk_engine.py`)
- Pre-trade validation
- Position sizing calculations
- Leverage limits
- Exposure checks

**Risk Layers**:
1. Pre-trade validation (reject invalid signals)
2. Position sizing (calculate safe size)
3. Drawdown monitoring (track equity)
4. Kill switch (emergency stop)
5. Daily loss limits (reset daily)

### 9. Database Manager (`app/database/db_manager.py`)
**Purpose**: Persistent storage for analytics (optional)

**Schema**:
- `trades`: Trade history with full details
- `positions`: Historical position data
- `analytics`: Performance metrics
- `risk_events`: Risk manager events

**Features**:
- Async PostgreSQL with asyncpg
- Connection pooling
- Automatic schema initialization
- Trade journaling

### 10. Telegram Bot (`app/telegram_bot.py`)
**Purpose**: User interface and notifications

**Commands**:
- `/start`: Activate notifications
- `/status`: Bot and market status
- `/position`: Current positions
- `/balance`: Account balance
- `/stats`: Trading statistics
- `/stop`: Emergency stop
- `/resume`: Resume trading

**Notifications**:
- Position opened/closed
- Order fills
- Risk events
- Kill switch triggers
- Errors and warnings

---

## Data Flow

### Trade Execution Flow

```
1. Main Loop (1s interval)
   └─▶ Get market data
       └─▶ Calculate indicators
           └─▶ Generate signal
               └─▶ Validate with risk manager
                   ├─▶ REJECT ──▶ Continue loop
                   └─▶ APPROVE
                       └─▶ Calculate position size
                           └─▶ Place OCO order (entry + SL + TP)
                               ├─▶ SUCCESS ──▶ Track position
                               └─▶ FAIL ──▶ Log error, continue
```

### Position Monitoring Flow

```
1. WebSocket Event: Order Fill
   └─▶ Update position state
       └─▶ Check if entry filled
           ├─▶ YES: SL/TP now active
           │   └─▶ Enable trailing stop (optional)
           │       └─▶ Monitor price updates
           │           └─▶ Adjust SL if profit increases
           └─▶ Check if SL/TP filled
               └─▶ Position closed
                   ├─▶ Record trade
                   ├─▶ Update statistics
                   ├─▶ Set cooldown timer (30s)
                   └─▶ Send Telegram notification
```

### Risk Management Flow

```
1. Before Trade
   └─▶ Check kill switch
       ├─▶ TRIGGERED: Reject trade
       └─▶ ACTIVE
           └─▶ Validate position count
               └─▶ Validate leverage
                   └─▶ Calculate max position size
                       └─▶ Check daily loss limit
                           ├─▶ ANY FAIL: Reject
                           └─▶ ALL PASS: Approve

2. During Trade
   └─▶ Monitor account value every loop
       └─▶ Calculate current drawdown
           ├─▶ Below warning: Continue
           ├─▶ At warning: Send alert
           └─▶ At critical: TRIGGER KILL SWITCH
               └─▶ Close all positions
                   └─▶ Stop trading
                       └─▶ Send emergency notification
```

---

## Module Details

### Technical Indicators (`app/indicators/technical_indicators.py`)

Provides comprehensive technical analysis toolkit:

**Trend Indicators**:
- SMA (Simple Moving Average)
- EMA (Exponential Moving Average)
- MACD (Moving Average Convergence Divergence)

**Momentum Indicators**:
- RSI (Relative Strength Index)
- Stochastic Oscillator
- Rate of Change (ROC)

**Volatility Indicators**:
- Bollinger Bands
- ATR (Average True Range)
- Standard Deviation

**Volume Indicators**:
- Volume-Weighted Average Price (VWAP)
- On-Balance Volume (OBV)

**Usage**:
```python
indicators = TechnicalIndicators()
indicators.update_data(candles)

# Generate signals
if indicators.rsi() < 30 and indicators.macd_signal() == 'bullish':
    signal = 'buy'
```

### Position Calculator (`app/utils/position_calculator.py`)

Calculates optimal position sizes considering:
- Account equity
- Leverage
- Risk percentage
- Market conditions
- Existing positions

**Formula**:
```python
position_size = (account_equity * position_size_pct * leverage) / entry_price
```

### Error Handler (`app/utils/error_handler.py`)

Centralized error handling with:
- Error classification (API, network, validation)
- Retry logic with exponential backoff
- Error logging and reporting
- Graceful degradation

**Pattern**:
```python
@handle_errors(retries=3, backoff=2.0)
async def risky_operation():
    # May fail, will retry automatically
    pass
```

### Trading Logger (`app/utils/trading_logger.py`)

Specialized logging for trading:
- Structured log format
- Separate files for different log levels
- Automatic rotation
- Sensitive data suppression

---

## Design Patterns

### 1. Dependency Injection
Components receive dependencies through constructor:
```python
order_manager = LighterOrderManager(client)
market_data = MarketData(api_client)
```

### 2. Observer Pattern
WebSocket implements observer for real-time updates:
```python
async def on_order_fill(event):
    # Handle event
    pass

ws.subscribe_account(on_order_fill)
```

### 3. Strategy Pattern
Pluggable strategies:
```python
strategy = ScalpingStrategy() if mode == 'scalp' else SwingStrategy()
signal = strategy.generate_signal(market_data)
```

### 4. Singleton Pattern
Global instances for shared resources:
```python
_credentials = None

def get_credentials():
    global _credentials
    if _credentials is None:
        _credentials = Credentials()
    return _credentials
```

### 5. Factory Pattern
Create components based on configuration:
```python
def create_strategy(mode):
    if mode == 'rule_based':
        return RuleBasedStrategy()
    elif mode == 'ml_based':
        return MLStrategy()
```

---

## Performance Characteristics

### API Efficiency
- **OCO Orders**: 1 call vs 3 calls (67% reduction)
- **Market Data**: Cached for 5s (reduces redundant calls)
- **WebSocket**: Push instead of poll (eliminates periodic requests)

### Latency Profile
- **Main Loop**: 1-second interval
- **Order Placement**: 200-500ms average
- **WebSocket Updates**: <100ms
- **Indicator Calculation**: <50ms
- **Risk Validation**: <10ms

### Resource Usage
- **CPU**: ~5% idle, ~20% during active trading
- **Memory**: ~100MB base, ~200MB with ML
- **Network**: ~1KB/s idle, ~50KB/s active
- **Disk**: ~10MB/day logs

### Scalability
- **Single Bot**: 1 market, 1-2 positions
- **Multi-Market**: Deploy separate instances per market
- **High Frequency**: Main loop can be reduced to 0.1s
- **ML Training**: Background process, doesn't block trading

---

## Security Architecture

### Authentication
- Private keys stored in environment variables
- Never logged or transmitted in cleartext
- Separate keys for testnet and mainnet

### Authorization
- Account-specific API keys
- Read/write permissions separated where possible
- Telegram bot validates chat IDs

### Data Protection
- Sensitive data suppressed in logs
- Database passwords encrypted
- PII excluded from analytics

### Network Security
- HTTPS only for API calls
- WSS (secure WebSocket) only
- No inbound connections required
- Firewall-friendly (outbound only)

### Operational Security
- Kill switch prevents runaway losses
- Daily loss limits reset automatically
- Position size limits prevent over-leverage
- Cooldown timers prevent rapid entries

### Audit Trail
- All trades logged with timestamps
- Risk events recorded
- Configuration changes tracked
- Error events preserved

---

## Extension Points

### Adding New Strategies
1. Create class in `app/strategies/rule_based/`
2. Implement `generate_signal(market_data)` method
3. Register in `strategy_manager.py`

### Adding New Indicators
1. Add method to `TechnicalIndicators` class
2. Test with historical data
3. Use in strategy logic

### Adding New Risk Checks
1. Create validator in `RiskEngine`
2. Add to validation chain
3. Configure thresholds in credentials

### Adding New Data Sources
1. Create API client in `app/lighter/`
2. Integrate with market data module
3. Update strategy to use new data

---

## Testing Strategy

### Unit Tests
- Component isolation
- Mock external dependencies
- Test edge cases

### Integration Tests
- Component interaction
- API connectivity
- Database operations

### Live Testing
- Testnet environment
- Small position sizes
- Full system validation

### Performance Tests
- Load testing
- Latency measurement
- Resource profiling

---

## Maintenance

### Regular Tasks
- **Daily**: Check logs for errors
- **Weekly**: Review trading statistics
- **Monthly**: Database cleanup, log rotation
- **Quarterly**: Dependency updates, security audit

### Monitoring Checklist
- [ ] Bot running and responsive
- [ ] No repeated errors in logs
- [ ] WebSocket connected
- [ ] API latency normal
- [ ] Account value tracking correctly
- [ ] Kill switch not triggered

### Upgrade Process
1. Test on testnet
2. Backup configuration and data
3. Deploy during low-volatility period
4. Monitor for 1 hour post-deployment
5. Rollback if issues detected

---

## Further Reading

- **DEPLOYMENT.md**: Production deployment guide
- **API.md**: Integration and API reference
- **V2_PERFORMANCE_REPORT.md**: SDK refactor performance analysis
- **Lighter Protocol Docs**: https://docs.lighter.xyz

---

**Version**: 1.0.0  
**Last Updated**: November 2025  
**Maintainer**: LighterBot Development Team
