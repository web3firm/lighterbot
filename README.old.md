# Lighter Trading Bot

Automated trading bot for Lighter perpetual futures exchange using the official Python SDK.

## Features

- ✅ Official Lighter Python SDK integration
- ✅ Async/await architecture for high performance
- ✅ Market data fetching (orderbook, trades, funding rates, candlesticks)
- ✅ Order management (limit, market, cancel)
- ✅ Position tracking and management
- ✅ Risk management (leverage limits, stop loss, take profit)
- ✅ Comprehensive logging
- ✅ Alert system integration

## Installation

```bash
# Clone or navigate to project directory
cd /root/lighterbot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Edit `.env` with your credentials:

```bash
# Lighter API Configuration
LIGHTER_BASE_URL=https://testnet.zklighter.elliot.ai  # or https://mainnet.zklighter.elliot.ai
LIGHTER_API_KEY_PRIVATE_KEY=your_private_key_here
LIGHTER_ACCOUNT_INDEX=your_account_index
LIGHTER_API_KEY_INDEX=253  # Default API key index

# Trading Configuration
TRADING_MARKET_ID=0  # 0 for BTC-PERP
MAX_POSITION_SIZE=1.0
MAX_LEVERAGE=10
MAX_DAILY_DRAWDOWN=0.05
LIQUIDATION_THRESHOLD=5.0
MAX_OPEN_ORDERS=5

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/lighter_bot.log
```

### Getting Your API Credentials

From the official Lighter SDK, you need:

1. **LIGHTER_API_KEY_PRIVATE_KEY**: Your Ethereum private key (hex format, with or without 0x prefix)
2. **LIGHTER_ACCOUNT_INDEX**: Your account index on Lighter (integer, e.g., 2)
3. **LIGHTER_API_KEY_INDEX**: API key index (default is 253)

These credentials authenticate your account to place orders and manage positions.

## Project Structure

```
/root/lighterbot/
├── config.py              # Configuration management
├── lighter_client.py      # Lighter SDK client wrapper
├── market_data.py         # Market data fetching
├── order_manager.py       # Order and position management
├── risk_manager.py        # Risk checks and monitoring
├── logger.py              # Logging system
├── main.py                # Main bot orchestrator
├── strategy.py            # Trading strategies
├── test_connection.py     # Connection test script
├── utils.py               # Utility functions
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create this)
└── logs/                  # Log files directory
```

## Usage

### Test Connection

First, test your API connection:

```bash
python test_connection.py
```

Expected output (with valid credentials):
```
=== Testing Lighter API ===
URL: https://testnet.zklighter.elliot.ai
Market ID: 0
Account Index: 2

✓ Client initialized
✓ Account: {...}
✓ Orderbook retrieved
✓ Funding: [...]

✓✓✓ All tests passed! ✓✓✓
```

### Run the Bot

```bash
python main.py
```

The bot will:
1. Initialize connection to Lighter
2. Load configuration from `.env`
3. Start monitoring markets and positions
4. Run simple strategy (take profit at +2%, stop loss at -1%)
5. Display status every 5 minutes

## SDK Integration Details

This bot uses the official `lighter-python` SDK from https://github.com/elliottech/lighter-python

### Key SDK Classes Used

- **SignerClient**: For authenticated operations (placing/cancelling orders)
- **ApiClient**: For public data (orderbooks, trades)
- **OrderApi**: Order-related endpoints
- **AccountApi**: Account information
- **CandlestickApi**: Historical data and funding rates

### Order Placement

Orders use integer values for size and price:
- **Base Amount**: Multiply by 1,000,000 (6 decimals)
- **Price**: Multiply by 100 (2 decimals)

Example: To buy 0.1 BTC at $50,000:
```python
base_amount = int(0.1 * 1_000_000)  # 100000
price = int(50000 * 100)              # 5000000
```

### Market IDs

- `0`: BTC-PERP
- Other markets: Check Lighter documentation

## Architecture

### Async/Await Pattern

All SDK calls are async:

```python
import asyncio
from lighter_client import get_client

async def example():
    client = await get_client()
    orderbook = await client.get_order_book_details(0)
    print(orderbook)

asyncio.run(example())
```

### Client Management

The bot maintains a global client instance:
- `get_client()`: Returns singleton client
- `close_client()`: Closes connections

### Error Handling

All API calls are wrapped with try/except and logging:
```python
try:
    result = await client.some_operation()
    if error:
        logger.error(f"Operation failed: {error}")
except Exception as e:
    logger.error(f"Exception: {e}", exc_info=True)
```

## Risk Management

The bot includes several risk protections:

1. **Position Size Limits**: Max position size per market
2. **Leverage Limits**: Maximum leverage allowed
3. **Stop Loss**: Automatic stop loss at -1% (configurable)
4. **Take Profit**: Automatic take profit at +2% (configurable)
5. **Daily Drawdown**: Max daily loss threshold
6. **Liquidation Monitoring**: Alerts when near liquidation

Configure limits in `.env`:
```bash
MAX_POSITION_SIZE=1.0
MAX_LEVERAGE=10
MAX_DAILY_DRAWDOWN=0.05  # 5%
LIQUIDATION_THRESHOLD=5.0  # 5% from liquidation price
```

## Logging

Logs are written to:
- **Console**: INFO level and above
- **File**: All levels (specified in LOG_LEVEL)

Log file location: `logs/lighter_bot.log`

Example log entry:
```
2025-11-10 11:00:00 - LighterBot - INFO - Bot started successfully
2025-11-10 11:00:01 - LighterBot - DEBUG - Fetched orderbook for market 0
2025-11-10 11:00:02 - LighterBot - INFO - Placed limit order: buy 0.1 @ 50000.0
```

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
