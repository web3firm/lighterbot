# 🚀 Advanced Lighter Trading Bot# Lighter Trading Bot



Production-ready algorithmic trading bot with multiple advanced strategies, comprehensive risk management, and real-time monitoring.Automated trading bot for Lighter perpetual futures exchange using the official Python SDK.



## ✅ Completed Upgrades## Features



### 1. Cleaned Up Codebase- ✅ Official Lighter Python SDK integration

- ✅ Removed all debug/credential helper scripts- ✅ Async/await architecture for high performance

- ✅ Streamlined configuration (no warnings)- ✅ Market data fetching (orderbook, trades, funding rates, candlesticks)

- ✅ Production-ready code only- ✅ Order management (limit, market, cancel)

- ✅ Position tracking and management

### 2. Advanced Trading Strategies- ✅ Risk management (leverage limits, stop loss, take profit)

- ✅ **Momentum Strategy**: RSI + MACD + EMA trend following- ✅ Comprehensive logging

- ✅ **Mean Reversion**: Bollinger Bands + RSI overbought/oversold- ✅ Alert system integration

- ✅ **Market Making**: Dynamic spreads based on volatility (optional)

- ✅ **Grid Trading**: Profit from ranging markets (optional)## Installation



### 3. Professional Risk Management```bash

- ✅ **Kelly Criterion Position Sizing**: Optimal bet sizing based on win rate# Clone or navigate to project directory

- ✅ **Auto Stop-Loss**: Closes positions at -2% loss automaticallycd /root/lighterbot

- ✅ **Auto Take-Profit**: Closes positions at +4% profit automatically  

- ✅ **Portfolio Heat Monitoring**: Tracks total exposure vs capital# Create virtual environment

- ✅ **Drawdown Protection**: Halts trading if daily loss limit exceededpython3 -m venv venv

- ✅ **Dynamic Position Sizing**: Adjusts size based on risk and account balancesource venv/bin/activate



### 4. Technical Analysis Suite# Install dependencies

- ✅ RSI, MACD, EMA/SMA, Bollinger Bandspip install -r requirements.txt

- ✅ ATR, Stochastic Oscillator, OBV```

- ✅ Real-time indicator calculations

## Configuration

## 🎯 Quick Start

1. Copy `.env.example` to `.env`:

### Run the Bot```bash

```bashcp .env.example .env

cd /root/lighterbot```

./venv/bin/python main.py

```2. Edit `.env` with your credentials:



### Current Configuration```bash

- **Network**: Mainnet (⚠️ REAL MONEY)# Lighter API Configuration

- **Account**: 366730LIGHTER_BASE_URL=https://testnet.zklighter.elliot.ai  # or https://mainnet.zklighter.elliot.ai

- **Symbol**: BTC-PERPLIGHTER_API_KEY_PRIVATE_KEY=your_private_key_here

- **Balance**: ~$59 collateral, ~$28 availableLIGHTER_ACCOUNT_INDEX=your_account_index

- **Current Position**: 15,510 PENGU (-$0.54 PnL)LIGHTER_API_KEY_INDEX=253  # Default API key index



## ⚙️ Strategy Configuration# Trading Configuration

TRADING_MARKET_ID=0  # 0 for BTC-PERP

Edit `main.py` to enable/disable strategies:MAX_POSITION_SIZE=1.0

MAX_LEVERAGE=10

```pythonMAX_DAILY_DRAWDOWN=0.05

# Currently enabled:LIQUIDATION_THRESHOLD=5.0

self.strategy_manager.add_strategy(MomentumStrategy())MAX_OPEN_ORDERS=5

self.strategy_manager.add_strategy(MeanReversionStrategy())

# Logging

# Available (commented out):LOG_LEVEL=INFO

# self.strategy_manager.add_strategy(MarketMakingStrategy())LOG_FILE=logs/lighter_bot.log

# self.strategy_manager.add_strategy(GridTradingStrategy())```

```

### Getting Your API Credentials

## 🛡️ Risk Settings (`.env`)

From the official Lighter SDK, you need:

```bash

MAX_POSITION_SIZE=0.01        # Max position size1. **LIGHTER_API_KEY_PRIVATE_KEY**: Your Ethereum private key (hex format, with or without 0x prefix)
# 🚀 Lighter Trading Bot (Advanced Edition)

Production-ready algorithmic trading bot for Lighter perpetual futures built on the official `lighter-python` SDK. Includes multi-strategy signal engine, layered resilience (circuit breaker + exponential backoff), persistent order indexing, dynamic market metadata, and comprehensive risk management.

---

## ✅ Core Capabilities

**Trading & Strategies**
- Momentum (RSI / MACD / EMAs)
- Mean Reversion (Bollinger / RSI extremes)
- Order Flow (order book + recent trades)
- Sentiment (news / social score placeholder)
- Optional: Market Making & Grid (disabled by default)

**Risk & Safety**
- Position size limits, max leverage, daily drawdown guard
- Kelly fraction sizing + portfolio heat monitoring
- Auto stop-loss / take-profit + liquidation proximity alerts
- DRY_RUN mode (simulation without sending signed transactions)

**Resilience Stack**
- Async architecture (Python 3.13 compatible)
- Circuit breaker guarding critical SDK calls
- Exponential backoff retry with jitter
- Concurrency throttling via semaphore in order management
- Persistent `OrderIndexer` (monotonic client order IDs)
- Dynamic `MarketMetadata` (base/price decimals resolved at runtime)

**Operational Quality**
- Structured logging + alert hook support
- Test suite (utilities, circuit breaker, OCO flow)
- Linting (Ruff) green baseline
- Type checking (mypy – staged hardening plan)

---

## 🗂 Project Structure (key files)

```
lighterbot/
├── config.py           # Pydantic settings w/ validators
├── lighter_client.py   # SDK wrapper (SignerClient + APIs)
├── order_manager.py    # Order placement, OCO, DRY_RUN safety
├── market_data.py      # Mid-price, bid/ask, market snapshots
├── risk_manager.py     # Advanced risk + auto position actions
├── strategies.py       # Strategy implementations & manager
├── utils.py            # CircuitBreaker, retry_async, metadata
├── main.py             # Bot orchestrator loop
├── tests/              # Pytest + pytest-asyncio tests
├── requirements.txt    # Dependencies
├── pyproject.toml      # Ruff configuration
├── mypy.ini            # Type checking config
└── README.md           # This documentation
```

---

## ⚙️ Installation

```bash
git clone <repo> lighterbot
cd lighterbot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## � Configuration (`.env`)

Copy `.env.example` (if present) or create manually:

```
LIGHTER_BASE_URL=https://mainnet.zklighter.elliot.ai    # Use testnet URL for safety first
LIGHTER_WS_URL=wss://mainnet.zklighter.elliot.ai/ws
LIGHTER_API_KEY_PRIVATE_KEY=<YOUR_API_KEY_PRIVATE_KEY>
LIGHTER_ACCOUNT_INDEX=<YOUR_ACCOUNT_INDEX>
LIGHTER_API_KEY_INDEX=2

TRADING_SYMBOL=BTC-PERP
TRADING_MARKET_ID=1              # Resolved at runtime; config default matches BTC-PERP
MAX_POSITION_SIZE=0.003
MAX_LEVERAGE=5
MAX_DAILY_DRAWDOWN=0.05
MIN_ORDER_SIZE=0.001

LIQUIDATION_THRESHOLD=0.2        # Alert if within 20% of liquidation
MAX_OPEN_ORDERS=3
POSITION_CHECK_INTERVAL=60

ENABLE_MOMENTUM_STRATEGY=true
ENABLE_MEAN_REVERSION_STRATEGY=true
ENABLE_MARKET_MAKING_STRATEGY=false
ENABLE_GRID_TRADING_STRATEGY=false
ENABLE_ORDERFLOW_STRATEGY=true
ENABLE_SENTIMENT_STRATEGY=true

API_RETRY_LIMIT=3
API_TIMEOUT=30
API_INITIAL_DELAY=1.0
API_MAX_DELAY=30.0

CB_FAILURE_THRESHOLD=5
CB_RESET_TIMEOUT=60
CB_HALF_OPEN_MAX_CALLS=1

DRY_RUN=true        # ← Start with true (NO real trades)
USE_TESTNET=true    # ← Use testnet first

LOG_LEVEL=INFO
LOG_FILE=logs/bot.log
```

> Set `DRY_RUN=false` only after validating behavior; keep `USE_TESTNET=true` until production ready.

---

## ▶️ Running the Bot

1. Validate credentials (or leave DRY_RUN true):
   ```bash
   ./venv/bin/python test_connection.py
   ```
2. Start trading loop:
   ```bash
   ./venv/bin/python main.py
   ```
3. Tail logs:
   ```bash
   tail -f logs/bot.log
   ```
4. Graceful shutdown: `Ctrl + C`

On startup the bot resolves market metadata; if configured `TRADING_MARKET_ID` mismatches resolved ID it logs a warning and overwrites it.

---

## 🧮 Order Decimal Conversion

`MarketMetadata` dynamically loads:
- Base amount decimals (e.g. 6 → multiply size by 1_000_000)
- Price decimals (e.g. 2 → multiply price by 100)

Helpers in `utils.py` ensure consistent integer conversions for all order paths (limit, market, stop-loss, take-profit, OCO).

---

## 🧷 Advanced Orders

Implemented wrappers in `lighter_client.py` & orchestration in `order_manager.py`:
- Stop-Loss limit
- Take-Profit limit
- Grouped OCO (One Cancels the Other) pair (TP + SL) with reduce-only defaults

In DRY_RUN mode these paths simulate placements without submitting signed txs.

---

## 🛡 Risk Management Highlights

`AdvancedRiskManager` provides:
- Portfolio heat calculation
- Kelly fraction sizing
- Daily drawdown tracking
- Auto close logic for extreme risk or SL/TP triggers
- Position conflict prevention (won’t open opposing side while active)

---

## 🔄 Resilience Flow

Call chain for critical SDK ops:
```
@circuit_breaker -> @retry_async -> lighter SDK async call
```
Circuit breaker short-circuits after configured failures; half-open probing limits risk; retry adds exponential backoff with cap.

---

## 🧪 Testing & Quality Gates

Run tests:
```bash
pytest -q
```

Current coverage includes:
- Circuit breaker state transitions
- Retry/backoff behavior
- Market metadata resolution & indexing
- OCO order placement (DRY_RUN path)

Linting:
```bash
ruff check .
```

Type checking (permissive baseline):
```bash
mypy .
```

Planned: tighten mypy ignore set & re-enable stricter Ruff rules incrementally.

---

## ⚠️ Safety Checklist

Before enabling real trading:
1. Use testnet + DRY_RUN for initial  session
2. Confirm market metadata decimals
3. Review risk limits (drawdown, leverage, liquidation threshold)
4. Validate OCO protective orders appear as expected
5. Enable only intended strategies; disable experimental ones
6. Monitor logs for circuit breaker open events (investigate root cause)

> Never deploy with placeholder or shared API keys. Protect secrets.

---

## � Customization

Enable/disable strategies via `.env` flags. Strategy parameters (RSI bounds, Bollinger periods, etc.) are in `strategies.py`. Add new strategies by subclassing `BaseStrategy` and registering with `StrategyManager.add_strategy(...)`.

Indicator extensions: place reusable logic in `indicators.py` and feed results into strategy `generate_signal` implementations.

---

## 🛠 Troubleshooting

| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| api key not found | Wrong private key / index | Verify `LIGHTER_API_KEY_PRIVATE_KEY`, `LIGHTER_ACCOUNT_INDEX`, `LIGHTER_API_KEY_INDEX` |
| Cannot connect host | Network / wrong URL | Switch to testnet URL or check connectivity |
| insufficient margin | Position too large | Reduce `MAX_POSITION_SIZE` or deposit collateral |
| Circuit breaker OPEN | Persistent endpoint failures | Inspect logs, increase `API_MAX_DELAY`, validate host |
| Orders not appearing (DRY_RUN) | DRY_RUN enabled | Set `DRY_RUN=false` after validation |

---

## � Roadmap / Next Steps
- Clean up Pydantic deprecation warnings (migrate Config → `model_config` / `ConfigDict`)
- Expand tests (risk manager edge cases, sentiment + orderflow strategies)
- Metrics endpoint / Prometheus integration
- Tighten mypy (remove broad ignores)
- Add performance benchmarking harness

---

## 📚 References
- Lighter Docs: https://docs.lighter.xyz
- SDK: https://github.com/elliottech/lighter-python
- Discord: https://discord.gg/lighter

---

_Last updated: 2025-11-11_

**Use responsibly. Start with testnet and DRY_RUN.**
## 📞 Quick Commands
