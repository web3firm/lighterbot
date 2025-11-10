# Lighter Trading Bot - Project Structure

```
lighterbot/
├── README.md                  # Comprehensive documentation
├── QUICKSTART.md             # Quick reference guide
├── requirements.txt          # Python dependencies
├── .env.example             # Environment configuration template
├── .gitignore               # Git ignore rules
├── start.sh                 # Quick start script
│
├── config.py                # Configuration management
│   └── Settings class with all bot parameters
│
├── api_client.py           # Lighter API client
│   ├── LighterAPIClient    # Main API client
│   │   ├── Request signing with private key
│   │   ├── Rate limiting
│   │   ├── Market data methods (public)
│   │   ├── Account methods (private)
│   │   └── Order methods
│   └── get_client()        # Factory function
│
├── market_data.py          # Market data management
│   ├── MarketData          # Market data fetcher
│   │   ├── get_current_price()
│   │   ├── get_orderbook()
│   │   ├── get_funding_rate()
│   │   └── calculate_funding_cost()
│   └── WebSocketFeed       # Real-time data feed
│       ├── Price updates
│       ├── Trade updates
│       └── Orderbook updates
│
├── order_manager.py        # Order and position management
│   ├── Order               # Order data class
│   ├── Position            # Position data class
│   └── OrderManager        # Order manager
│       ├── place_order()
│       ├── place_market_order()
│       ├── place_limit_order()
│       ├── cancel_order()
│       ├── cancel_all_orders()
│       ├── get_position()
│       ├── get_all_positions()
│       ├── close_position()
│       └── get_fills()
│
├── risk_manager.py         # Risk management
│   ├── RiskLimits          # Risk limit configuration
│   ├── RiskMetrics         # Current risk metrics
│   └── RiskManager         # Risk manager
│       ├── check_order_risk()
│       ├── check_liquidation_risk()
│       ├── calculate_safe_order_size()
│       ├── should_emergency_close()
│       └── monitor_positions()
│
├── strategy.py             # Trading strategies
│   ├── Signal              # Trading signal data class
│   ├── Strategy            # Base strategy class (ABC)
│   ├── EMACrossoverStrategy  # EMA crossover implementation
│   ├── MomentumStrategy    # Momentum strategy implementation
│   └── StrategyManager     # Multi-strategy manager
│       ├── add_strategy()
│       ├── enable_strategy()
│       ├── disable_strategy()
│       └── run_all()
│
├── logger.py               # Logging and monitoring
│   ├── BotLogger           # Structured logger
│   │   ├── log_order()
│   │   ├── log_fill()
│   │   ├── log_position()
│   │   ├── log_error()
│   │   └── log_risk_alert()
│   ├── AlertManager        # Alert/notification system
│   │   ├── send_alert()
│   │   ├── alert_order_filled()
│   │   ├── alert_high_risk()
│   │   └── alert_emergency()
│   ├── get_logger()        # Global logger factory
│   └── get_alert_manager() # Global alert manager factory
│
├── main.py                 # Main bot orchestrator
│   └── LighterBot          # Main bot class
│       ├── setup_strategies()
│       ├── setup_websocket()
│       ├── check_risk_and_positions()
│       ├── run_strategies()
│       ├── display_status()
│       ├── start()
│       └── stop()
│
├── utils.py                # Utility scripts
│   ├── test_api_connection()
│   ├── display_account_status()
│   ├── cancel_all_orders_confirm()
│   ├── close_all_positions_confirm()
│   ├── analyze_trade_logs()
│   ├── check_risk_status()
│   ├── get_funding_info()
│   └── main()              # Utility menu
│
└── logs/                   # Log directory (created at runtime)
    ├── bot.log            # Main application log
    ├── trades.jsonl       # Structured trade log
    ├── positions.jsonl    # Position updates log
    └── errors.jsonl       # Error log
```

## Module Dependencies

```
main.py
  ├── config.py
  ├── market_data.py
  │   ├── api_client.py
  │   └── config.py
  ├── order_manager.py
  │   ├── api_client.py
  │   └── config.py
  ├── risk_manager.py
  │   ├── order_manager.py
  │   └── market_data.py
  ├── strategy.py
  │   ├── market_data.py
  │   ├── order_manager.py
  │   └── risk_manager.py
  └── logger.py
      └── config.py
```

## Data Flow

```
Market Data → Strategy → Risk Check → Order Manager → API Client → Exchange
     ↓                        ↓             ↓                          ↓
  WebSocket              Risk Manager    Logger                  Execution
     ↓                        ↓             ↓                          ↓
  Callbacks               Alerts        JSONL Logs              Fills/Updates
```

## Execution Flow

1. **Initialization**
   - Load configuration from `.env`
   - Initialize API client with credentials
   - Setup market data feeds
   - Create order manager
   - Initialize risk manager
   - Setup strategies
   - Configure logging

2. **Main Loop** (every 10 seconds)
   - Fetch latest market data
   - Run all enabled strategies
   - Generate trading signals
   - Check risk for each signal
   - Execute approved orders
   - Log all actions

3. **Risk Monitoring** (every 60 seconds)
   - Check all open positions
   - Calculate risk metrics
   - Check liquidation risk
   - Trigger alerts if needed
   - Emergency close if necessary

4. **Shutdown**
   - Stop WebSocket feeds
   - Log final status
   - Send shutdown alert

## Key Features by Module

### api_client.py
- ✓ Request signing with eth-account
- ✓ Rate limiting (10 req/sec)
- ✓ Public endpoints (markets, prices, orderbook)
- ✓ Private endpoints (account, orders, positions)
- ✓ Error handling and retries

### market_data.py
- ✓ REST API for market data
- ✓ WebSocket for real-time feeds
- ✓ Price caching (5 second TTL)
- ✓ Funding rate tracking
- ✓ Funding cost calculation

### order_manager.py
- ✓ Market and limit orders
- ✓ Order lifecycle management
- ✓ Position tracking
- ✓ Fill monitoring
- ✓ Bulk operations (cancel all)

### risk_manager.py
- ✓ Position size limits
- ✓ Leverage limits
- ✓ Daily drawdown protection
- ✓ Liquidation risk monitoring
- ✓ Margin ratio checks
- ✓ Safe order size calculation
- ✓ Emergency close logic

### strategy.py
- ✓ Abstract Strategy base class
- ✓ EMA Crossover implementation
- ✓ Momentum strategy implementation
- ✓ Signal generation framework
- ✓ Multi-strategy management
- ✓ Enable/disable strategies

### logger.py
- ✓ Structured logging (JSONL)
- ✓ Separate logs for trades/positions/errors
- ✓ Alert system with throttling
- ✓ Webhook notifications
- ✓ Console and file output

### main.py
- ✓ Complete bot orchestration
- ✓ Strategy coordination
- ✓ Risk monitoring
- ✓ Status display
- ✓ Graceful shutdown
- ✓ Signal handling

### utils.py
- ✓ API connection testing
- ✓ Account status display
- ✓ Risk status checking
- ✓ Emergency operations
- ✓ Log analysis
- ✓ Funding information

## Configuration Parameters

See `.env.example` for all configurable parameters:
- API credentials and endpoints
- Trading symbol and limits
- Risk management thresholds
- Logging configuration
- Environment selection

## Testing Strategy

1. **Unit Testing** - Test individual modules
2. **Integration Testing** - Test API connectivity
3. **Paper Trading** - Run on testnet
4. **Small Size Testing** - Start with minimal position
5. **Live Monitoring** - Watch closely for 24h

## Security Considerations

- API keys stored in `.env` (not committed)
- Sub-account isolation
- Request signing for authentication
- Rate limiting to prevent abuse
- Risk limits to prevent overexposure
- Emergency shutdown mechanisms

## Performance Optimization

- Price caching (5s TTL)
- Rate limiting (100ms between requests)
- WebSocket for real-time data
- JSONL for efficient log storage
- Batch operations where possible

## Extensibility

To add new strategies:
1. Extend `Strategy` base class
2. Implement `generate_signal()` method
3. Add to `StrategyManager` in `main.py`

To add new risk checks:
1. Add to `RiskManager.check_order_risk()`
2. Define limits in `RiskLimits`
3. Update configuration in `.env`

To add new alerts:
1. Add method to `AlertManager`
2. Call from appropriate location
3. Configure webhook in `.env`
