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

MAX_LEVERAGE=10               # Max leverage  2. **LIGHTER_ACCOUNT_INDEX**: Your account index on Lighter (integer, e.g., 2)

MAX_DAILY_DRAWDOWN=0.05       # 5% daily loss limit3. **LIGHTER_API_KEY_INDEX**: API key index (default is 253)

MIN_ORDER_SIZE=0.001          # Min order size

LIQUIDATION_THRESHOLD=0.8     # Liquidation alert thresholdThese credentials authenticate your account to place orders and manage positions.

MAX_OPEN_ORDERS=10            # Max concurrent orders

```## Project Structure



## 📊 Bot Features```

/root/lighterbot/

### Real-Time Monitoring├── config.py              # Configuration management

- Live position tracking with P&L├── lighter_client.py      # Lighter SDK client wrapper

- Portfolio heat (risk exposure)├── market_data.py         # Market data fetching

- Win rate and performance metrics├── order_manager.py       # Order and position management

- Automatic alerts for high-risk situations├── risk_manager.py        # Risk checks and monitoring

├── logger.py              # Logging system

### Automated Position Management├── main.py                # Main bot orchestrator

```├── strategy.py            # Trading strategies

Stop-Loss: -2%  → Auto-close on losses├── test_connection.py     # Connection test script

Take-Profit: +4% → Auto-close on wins├── utils.py               # Utility functions

```├── requirements.txt       # Python dependencies

├── .env                   # Environment variables (create this)

### Signal Generation└── logs/                  # Log files directory

- Multiple strategies analyze market simultaneously```

- Consensus mechanism combines signals

- Strength-based position sizing## Usage

- Conflict detection (won't open opposing positions)

### Test Connection

### Performance Tracking

- Trade count and win rateFirst, test your API connection:

- Kelly Criterion optimization

- Daily drawdown monitoring```bash

- Total P&L trackingpython test_connection.py

```

## 📈 How It Works

Expected output (with valid credentials):

1. **Market Analysis** (every 60s)```

   - Fetches current prices=== Testing Lighter API ===

   - Updates technical indicatorsURL: https://testnet.zklighter.elliot.ai

   - All strategies analyze marketMarket ID: 0

   - Generates consensus signalAccount Index: 2



2. **Risk Check** (before every trade)✓ Client initialized

   - Kelly Criterion position sizing✓ Account: {...}

   - Portfolio heat validation✓ Orderbook retrieved

   - Drawdown limit check✓ Funding: [...]

   - Order count verification

✓✓✓ All tests passed! ✓✓✓

3. **Order Execution**```

   - Places market orders

   - Sets stop-loss/take-profit levels### Run the Bot

   - Tracks in performance history

```bash

4. **Position Monitoring** (every 5min)python main.py

   - Auto stop-loss/take-profit```

   - Liquidation risk alerts

   - Performance statistics updateThe bot will:

1. Initialize connection to Lighter

## ⚠️ Important Safety Notes2. Load configuration from `.env`

3. Start monitoring markets and positions

### You Are Trading on MAINNET4. Run simple strategy (take profit at +2%, stop loss at -1%)

- This is NOT a simulation5. Display status every 5 minutes

- Real funds are at risk

- Start with VERY SMALL positions## SDK Integration Details



### Recommended for First RunThis bot uses the official `lighter-python` SDK from https://github.com/elliottech/lighter-python

```bash

# In .env, set conservative limits:### Key SDK Classes Used

MAX_POSITION_SIZE=0.001      # Tiny positions

MAX_DAILY_DRAWDOWN=0.02      # 2% daily limit- **SignerClient**: For authenticated operations (placing/cancelling orders)

```- **ApiClient**: For public data (orderbooks, trades)

- **OrderApi**: Order-related endpoints

### Monitor Closely- **AccountApi**: Account information

```bash- **CandlestickApi**: Historical data and funding rates

# Watch logs in real-time:

tail -f logs/bot.log### Order Placement



# Check status (press Ctrl+C to stop bot gracefully)Orders use integer values for size and price:

```- **Base Amount**: Multiply by 1,000,000 (6 decimals)

- **Price**: Multiply by 100 (2 decimals)

## 🎛️ Customization

Example: To buy 0.1 BTC at $50,000:

### Adjust Strategy Parameters```python

base_amount = int(0.1 * 1_000_000)  # 100000

**Momentum Strategy** (`strategies.py`):price = int(50000 * 100)              # 5000000

```python```

self.rsi_oversold = 30       # Buy threshold

self.rsi_overbought = 70     # Sell threshold### Market IDs

self.ema_fast = 12           # Fast EMA period

self.ema_slow = 26           # Slow EMA period- `0`: BTC-PERP

```- Other markets: Check Lighter documentation



**Mean Reversion** (`strategies.py`):## Architecture

```python

self.bb_period = 20          # Bollinger Band period### Async/Await Pattern

self.bb_std = 2.0            # Standard deviations

```All SDK calls are async:



### Add Custom Indicators (`indicators.py`)```python

```pythonimport asyncio

@staticmethodfrom lighter_client import get_client

def my_custom_indicator(prices: List[float]) -> float:

    # Your calculation hereasync def example():

    return result    client = await get_client()

```    orderbook = await client.get_order_book_details(0)

    print(orderbook)

## 📁 File Structure

asyncio.run(example())

``````

lighterbot/

├── main.py              # Main bot (✅ upgraded)### Client Management

├── strategies.py        # Trading strategies (✅ new)

├── indicators.py        # Technical indicators (✅ new)The bot maintains a global client instance:

├── risk_manager.py      # Risk management (✅ upgraded)- `get_client()`: Returns singleton client

├── order_manager.py     # Order execution- `close_client()`: Closes connections

├── market_data.py       # Market data fetching

├── lighter_client.py    # Lighter SDK wrapper### Error Handling

├── config.py            # Configuration (✅ cleaned)

├── logger.py            # LoggingAll API calls are wrapped with try/except and logging:

├── .env                 # Your credentials```python

└── README.md            # This filetry:

```    result = await client.some_operation()

    if error:

## 🔄 Next Steps        logger.error(f"Operation failed: {error}")

except Exception as e:

1. **Test Run**: Start bot and watch for 1 hour    logger.error(f"Exception: {e}", exc_info=True)

2. **Monitor Signals**: Check what signals are generated```

3. **Review Trades**: Analyze first few trades

4. **Adjust Parameters**: Fine-tune based on performance## Risk Management

5. **Scale Gradually**: Increase position sizes slowly

The bot includes several risk protections:

## 📞 Quick Commands

1. **Position Size Limits**: Max position size per market

```bash2. **Leverage Limits**: Maximum leverage allowed

# Start bot3. **Stop Loss**: Automatic stop loss at -1% (configurable)

./venv/bin/python main.py4. **Take Profit**: Automatic take profit at +2% (configurable)

5. **Daily Drawdown**: Max daily loss threshold

# Test connection6. **Liquidation Monitoring**: Alerts when near liquidation

./venv/bin/python test_connection.py

Configure limits in `.env`:

# Watch logs```bash

tail -f logs/bot.logMAX_POSITION_SIZE=1.0

MAX_LEVERAGE=10

# Stop botMAX_DAILY_DRAWDOWN=0.05  # 5%

Press Ctrl+C (graceful shutdown)LIQUIDATION_THRESHOLD=5.0  # 5% from liquidation price

``````



## 🎉 Ready to Trade!## Logging



Your bot now has:Logs are written to:

- ✅ Advanced multi-strategy engine- **Console**: INFO level and above

- ✅ Professional risk management- **File**: All levels (specified in LOG_LEVEL)

- ✅ Auto stop-loss/take-profit

- ✅ Kelly Criterion position sizingLog file location: `logs/lighter_bot.log`

- ✅ Real-time monitoring

- ✅ Performance trackingExample log entry:

```

**Start the bot and monitor closely for the first few hours!**2025-11-10 11:00:00 - LighterBot - INFO - Bot started successfully

2025-11-10 11:00:01 - LighterBot - DEBUG - Fetched orderbook for market 0

---2025-11-10 11:00:02 - LighterBot - INFO - Placed limit order: buy 0.1 @ 50000.0

*Last updated: 2025-11-10 | Trading on Lighter Mainnet*```


## Troubleshooting

### API Key Not Found Error

```
Error: api key not found
```

**Solution**: Ensure your `LIGHTER_API_KEY_PRIVATE_KEY`, `LIGHTER_ACCOUNT_INDEX`, and `LIGHTER_API_KEY_INDEX` are correct in `.env`. You need actual credentials from your Lighter account.

### Connection Refused Error

```
Error: Cannot connect to host
```

**Solution**: Check your internet connection and verify `LIGHTER_BASE_URL` is correct.

### Insufficient Margin Error

```
Error: insufficient margin
```

**Solution**: Deposit funds to your Lighter account or reduce position size.

## Safety

**⚠️ IMPORTANT**: This bot trades real money. Use with caution.

- Start with testnet: `https://testnet.zklighter.elliot.ai`
- Test with small positions first
- Monitor the bot closely
- Set conservative risk limits
- Keep logs for debugging

## Summary of Changes

### Complete SDK Integration

1. **Removed custom API client** - Replaced with official lighter-python SDK
2. **Updated all modules** - Made async-compatible for SDK
3. **New authentication** - Uses private key + account_index + api_key_index pattern
4. **Updated endpoints** - Uses testnet.zklighter.elliot.ai instead of api.lighter.xyz
5. **Integer-based orders** - SDK requires integer values for size/price
6. **Market IDs** - Uses integer market_id (0 for BTC-PERP) instead of symbol strings

### Files Updated

- ✅ `requirements.txt` - Now installs from official SDK GitHub repo
- ✅ `config.py` - New auth fields (lighter_api_key_private_key, lighter_account_index, lighter_api_key_index, trading_market_id)
- ✅ `.env` - Updated with testnet URLs and new auth structure
- ✅ `lighter_client.py` - NEW: Wrapper for official SDK (SignerClient, ApiClient, OrderApi, etc.)
- ✅ `market_data.py` - Async methods using SDK
- ✅ `order_manager.py` - Async methods using SDK, integer-based orders
- ✅ `risk_manager.py` - Async methods
- ✅ `main.py` - Async main loop
- ✅ `utils.py` - Async utility functions
- ✅ `test_connection.py` - NEW: Simple connection test
- ❌ `api_client.py` - REMOVED (replaced by lighter_client.py)

## Next Steps

1. **Get valid API credentials** from your Lighter account
2. **Update .env** with your credentials
3. **Run test_connection.py** to verify connection
4. **Start with small positions** to test the bot
5. **Monitor logs** for any errors

## Support

- Lighter Docs: https://docs.lighter.xyz
- Lighter SDK: https://github.com/elliottech/lighter-python
- Lighter Discord: https://discord.gg/lighter

---

**Built with the official Lighter Python SDK v0.1.4**
