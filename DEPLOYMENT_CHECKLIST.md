# 🚀 Deployment Checklist for Production

This checklist ensures the Lighter trading bot is production-ready and properly configured.

## ✅ Pre-Deployment Validation

### 1. SDK Integration Verification
- [x] Official `lighter-python` SDK properly integrated
- [x] SignerClient initialized with correct parameters
- [x] Async patterns properly implemented across all modules
- [x] Error handling with tuple unpacking: `(CreateOrder, TxHash, error_str)`
- [x] Decimal conversions using dynamic MarketMetadata (not hardcoded)
- [x] Price string parsing handles SDK format: `"50000.00"` → `5000000 / 100`

### 2. Resilience & Safety
- [x] Circuit breaker configured and tested (5 failures, 60s reset)
- [x] Exponential backoff retry on critical API calls (3 attempts max)
- [x] Persistent order index to avoid collisions
- [x] Concurrency semaphore limiting simultaneous orders
- [x] DRY_RUN mode functional (simulates without real txs)
- [x] Config validators prevent unsafe settings

### 3. Testing Status
- [x] Unit tests passing (10/10 green)
- [x] Circuit breaker state transitions validated
- [x] Market metadata & indexer tested
- [x] OCO order placement tested (DRY_RUN path)
- [x] Async test markers properly configured

### 4. Code Quality
- [x] Linting passing (Ruff with configured rules)
- [x] Type checking configured (mypy with permissive baseline)
- [ ] Pydantic V2 deprecation warnings to be cleaned (future task)

---

## 🔧 Configuration Checklist

### Environment Setup
```bash
# 1. Create .env from template
cp .env.example .env

# 2. Edit .env with your credentials
nano .env
```

### Critical .env Settings
- [ ] **LIGHTER_API_KEY_PRIVATE_KEY** = Your API key private value (hex)
- [ ] **LIGHTER_ACCOUNT_INDEX** = Your account index (integer)
- [ ] **LIGHTER_API_KEY_INDEX** = Your API key index (default: 2)
- [ ] **TRADING_MARKET_ID** = Correct market ID (1 for BTC-PERP)
- [ ] **MAX_POSITION_SIZE** = Conservative size for first run (0.001)
- [ ] **MAX_LEVERAGE** = Safe leverage limit (≤5 recommended)
- [ ] **MAX_DAILY_DRAWDOWN** = Daily loss limit (0.05 = 5%)
- [ ] **LIQUIDATION_THRESHOLD** = Alert distance from liquidation (0.2 = 20%)
- [ ] **DRY_RUN** = Set to `true` for initial testing

### Network Selection
- [ ] **USE_TESTNET=true** for testnet.zklighter.elliot.ai
- [ ] **USE_TESTNET=false** for mainnet (after testnet validation)

### Strategy Configuration
```bash
ENABLE_MOMENTUM_STRATEGY=true      # RSI/MACD/EMA
ENABLE_MEAN_REVERSION_STRATEGY=true # Bollinger/RSI extremes
ENABLE_ORDERFLOW_STRATEGY=true     # Order book analysis
ENABLE_SENTIMENT_STRATEGY=true     # Social/news sentiment
ENABLE_MARKET_MAKING_STRATEGY=false # (Disable for safety)
ENABLE_GRID_TRADING_STRATEGY=false  # (Disable for safety)
```

---

## 🧪 Pre-Production Testing

### Phase 1: Connection Test
```bash
./venv/bin/python test_connection.py
```
**Expected:** Account details retrieved, orderbook fetched, no errors.

### Phase 2: DRY_RUN Mode
```bash
# In .env: DRY_RUN=true, USE_TESTNET=true
./venv/bin/python main.py
```
**Expected:** Bot starts, logs "[DRY RUN]" messages, no real orders submitted.

### Phase 3: Testnet with Real Orders
```bash
# In .env: DRY_RUN=false, USE_TESTNET=true, MAX_POSITION_SIZE=0.001
./venv/bin/python main.py
```
**Expected:** Small test orders execute on testnet, positions tracked, risk checks active.

### Phase 4: Monitor for 24 Hours
- [ ] Check logs for errors: `tail -f logs/bot.log`
- [ ] Verify circuit breaker doesn't trip frequently
- [ ] Confirm order indexer persists across restarts
- [ ] Validate risk manager auto-closes positions at SL/TP
- [ ] Ensure no memory leaks (monitor RSS)

---

## 📊 Mainnet Deployment Steps

### Step 1: Final Config Review
```bash
# Verify settings before mainnet
cat .env | grep -E "(LIGHTER_BASE_URL|USE_TESTNET|DRY_RUN|MAX_POSITION_SIZE|MAX_LEVERAGE)"
```
**Expected:**
```
LIGHTER_BASE_URL=https://mainnet.zklighter.elliot.ai
USE_TESTNET=false
DRY_RUN=false
MAX_POSITION_SIZE=0.003  # or your risk-appropriate size
MAX_LEVERAGE=5
```

### Step 2: Start with Conservative Limits
- [ ] Position size: Start at 0.001–0.003
- [ ] Leverage: Keep ≤5x initially
- [ ] Drawdown: 5% daily max
- [ ] Open orders: Limit to 3–5

### Step 3: Launch
```bash
# Run in screen or tmux for persistence
screen -S lighter-bot
./venv/bin/python main.py

# Detach: Ctrl+A, D
# Reattach: screen -r lighter-bot
```

### Step 4: Real-Time Monitoring (First 4 Hours)
```bash
# Watch logs
tail -f logs/bot.log

# In another terminal, check process
ps aux | grep python | grep main.py
```

**Monitor for:**
- [ ] Orders executing successfully
- [ ] Risk checks triggering appropriately
- [ ] No rapid circuit breaker trips
- [ ] Position updates reflect reality
- [ ] PnL tracking accurate

---

## 🛡 Safety Guardrails

### Automatic Protections Active
- ✅ **Circuit Breaker:** Trips after 5 consecutive API failures
- ✅ **Max Drawdown:** Halts trading if daily loss exceeds configured %
- ✅ **Auto Stop-Loss:** Closes positions at -2% (configurable)
- ✅ **Auto Take-Profit:** Closes positions at +4% (configurable)
- ✅ **Liquidation Alert:** Warns when within threshold distance
- ✅ **Order Limit:** Semaphore restricts concurrent order count

### Manual Kill Switch
```bash
# Graceful shutdown
pkill -SIGTERM -f "python main.py"

# Force kill (if needed)
pkill -9 -f "python main.py"

# Cancel all open orders via SDK
./venv/bin/python -c "
import asyncio
from lighter_client import get_client

async def cancel_all():
    client = await get_client()
    await client.cancel_all_orders()

asyncio.run(cancel_all())
"
```

---

## 📈 Post-Deployment Monitoring

### Daily Checks
- [ ] Review log file for errors: `grep ERROR logs/bot.log`
- [ ] Check circuit breaker events: `grep "Circuit breaker OPEN" logs/bot.log`
- [ ] Verify daily drawdown within limits
- [ ] Confirm order index file increments: `cat data/order_index.json`
- [ ] Validate positions match exchange UI

### Weekly Review
- [ ] Analyze win rate and Kelly fraction adjustments
- [ ] Review strategy performance (which signals profitable?)
- [ ] Check for Pydantic deprecation warnings (plan migration)
- [ ] Update dependencies if SDK has new release
- [ ] Backup logs and performance data

---

## 🔧 Troubleshooting

### Issue: Circuit Breaker Constantly Tripping
**Cause:** Network issues or SDK endpoint downtime  
**Action:** Increase `CB_FAILURE_THRESHOLD` or `API_MAX_DELAY`, check connectivity

### Issue: Orders Not Filling
**Cause:** Low liquidity or price moved before execution  
**Action:** Use market orders or widen limit order slippage tolerance

### Issue: "api key not found"
**Cause:** Wrong credentials in .env  
**Action:** Verify `LIGHTER_API_KEY_PRIVATE_KEY`, `LIGHTER_ACCOUNT_INDEX`, `LIGHTER_API_KEY_INDEX`

### Issue: Position data mismatch
**Cause:** Stale cache or API response parsing  
**Action:** Restart bot to refresh state, check `order_manager.py` position parsing

---

## 📝 Deployment Sign-Off

Before going live on mainnet with real capital:

- [ ] All tests pass (`pytest -q`)
- [ ] Testnet run completed successfully for 24+ hours
- [ ] Risk limits configured conservatively
- [ ] Logs reviewed for no critical errors
- [ ] Circuit breaker and retry confirmed working
- [ ] DRY_RUN disabled intentionally
- [ ] Monitoring alerts configured (if using webhook)
- [ ] Kill switch procedure documented and tested
- [ ] Backup of `.env` and `data/` stored securely

**Deployment Approved By:** _______________  
**Date:** _______________  
**Initial Capital:** _______________  
**Max Risk Per Trade:** _______________%  

---

## 🎯 Success Metrics (First Week)

Track these KPIs:
- **Uptime:** Target >99%
- **Win Rate:** Monitor vs. Kelly assumption
- **Max Drawdown:** Should stay below configured limit
- **Circuit Breaker Trips:** <5 per day acceptable
- **Average Trade Duration:** Track for strategy tuning
- **PnL:** Document for performance review

---

**Last Updated:** 2025-11-11  
**Bot Version:** Production-Ready with Official SDK  
**SDK Version:** lighter-python (latest from GitHub)
