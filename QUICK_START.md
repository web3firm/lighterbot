# 🚀 Quick Start Guide

## Running the Bot

### Option 1: Using the run script (Recommended)
```bash
./run_bot.sh
```

### Option 2: Manual activation
```bash
source venv/bin/activate
python main.py
```

### ⚠️ IMPORTANT: Don't use `python3 main.py` directly!

**This won't work:**
```bash
python3 main.py  # ❌ Won't find pydantic_settings
```

**Why?** The packages are installed in the virtual environment (`venv/`), not globally.

---

## What You'll See

When the bot starts successfully:
```
✓ Enabled: Momentum Strategy
✓ Enabled: Mean Reversion Strategy
✓ Enabled: Order Flow Strategy
✓ Enabled: Sentiment Strategy

Advanced Trading Bot initialized with 4 strategies
Trading BTC-PERP on market ID 1
```

Then every 60 seconds:
```
================================================================================
⚡ Advanced Trading Bot Status - 2025-11-10 15:21:26
================================================================================

💰 Account:
   Total Collateral: $59.93
   Available: $28.15

📊 Positions: 1
   PENGU: 15510 tokens ($249.88 value, -$0.54 PnL)

⚠️  Risk Metrics:
   Portfolio Heat: 24.5%
   Max Drawdown Today: 0.0%
   Win Rate: 50.0%
   Kelly Fraction: 0.06

📈 Performance:
   Uptime: 5.0 minutes
   Trades Executed: 0
   Active Strategies: 4
================================================================================
```

---

## Monitoring

### Watch live logs
```bash
tail -f logs/bot.log
```

### Watch strategy signals
```bash
tail -f logs/bot.log | grep -E "Order Flow|Sentiment|Consensus"
```

### Test strategies without trading
```bash
source venv/bin/activate
python test_new_strategies.py
```

---

## Stopping the Bot

Press `Ctrl+C` to stop gracefully:
```
^C
Shutdown signal received
Closing connections...
Goodbye!
```

---

## Configuration

Edit `.env` to customize:

```env
# Position sizing
MAX_POSITION_SIZE=0.003    # Max 0.003 BTC per trade
MAX_LEVERAGE=5             # 5x leverage

# Risk limits
LIQUIDATION_THRESHOLD=0.2  # Alert at 20% from liquidation
MAX_DAILY_DRAWDOWN=0.05    # Stop trading at 5% daily loss

# Enable/disable strategies
ENABLE_MOMENTUM_STRATEGY=true
ENABLE_MEAN_REVERSION_STRATEGY=true
ENABLE_ORDERFLOW_STRATEGY=true
ENABLE_SENTIMENT_STRATEGY=true
```

After editing `.env`, restart the bot.

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'pydantic_settings'"
```bash
# Solution: Use the run script or activate venv first
./run_bot.sh

# OR
source venv/bin/activate
python main.py
```

### "float division by zero"
This is normal when starting - happens when calculating win rate with 0 trades.
It will go away after the first trade.

### "Empty orderbook" warnings
These are expected - the bot uses trade data instead (this is normal and handled).

### Check if everything is working
```bash
source venv/bin/activate
python test_new_strategies.py
```

Should show:
- ✓ Order Flow signal
- ✓ Sentiment signal  
- ✓ Fear & Greed Index

---

## Quick Commands

```bash
# Start bot
./run_bot.sh

# Stop bot
Ctrl+C

# Test strategies
source venv/bin/activate && python test_new_strategies.py

# Check logs
tail -50 logs/bot.log

# Watch live
tail -f logs/bot.log

# Check account
source venv/bin/activate && python -c "
import asyncio
from lighter_client import get_client

async def check():
    client = await get_client()
    info = await client.get_account_info()
    print(info)
    await client.close()

asyncio.run(check())
"
```

---

## Current Setup

**Account:** 366730  
**Network:** Mainnet (REAL money!)  
**Market:** BTC-PERP (market_id=1)  
**Collateral:** $59.93  
**Strategies:** 4 active (Momentum, Mean Reversion, Order Flow, Sentiment)  

**The bot is READY TO TRADE!** 🚀
