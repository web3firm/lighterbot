# 🚀 QUICK REFERENCE CARD

## Essential Commands

### Setup & Configuration
```bash
# Copy and edit config
cp .env.example .env
nano .env

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Testing & Deployment
```bash
# Interactive deployment wizard
./deploy.sh

# Test API connection
python3 test_connection.py

# Run bot
./run_bot.sh

# Run tests
pytest -q
```

### Emergency Controls
```bash
# Graceful stop
pkill -SIGTERM -f "python main.py"

# Force kill
pkill -9 -f "python main.py"

# Cancel all orders
python3 -c "
import asyncio
from lighter_client import get_client
async def cancel_all():
    client = await get_client()
    await client.cancel_all_orders()
asyncio.run(cancel_all())
"
```

---

## Project Files

### Core Modules (12)
- `config.py` - Settings management
- `main.py` - Bot orchestrator  
- `lighter_client.py` - SDK wrapper
- `market_data.py` - Data fetching
- `order_manager.py` - Order execution
- `risk_manager.py` - Risk management
- `strategies.py` - 6 strategies
- `indicators.py` - Technical analysis
- `orderflow_analyzer.py` - Flow analysis
- `sentiment_analyzer.py` - Sentiment
- `logger.py` - Logging
- `utils.py` - Helpers

### Scripts
- `deploy.sh` - Deployment wizard
- `run_bot.sh` - Bot launcher
- `test_connection.py` - API test

### Documentation
- `README.md` - Main docs
- `DEPLOYMENT_CHECKLIST.md` - Deploy guide
- `PRODUCTION_READY.md` - Status
- `QUICK_REFERENCE.md` - This file

### Configuration
- `.env.example` - Testnet template
- `.env.production.example` - Mainnet template

---

## Configuration Quick Settings

### Testnet Safe Defaults
```bash
LIGHTER_BASE_URL=https://testnet.zklighter.elliot.ai
DRY_RUN=true
USE_TESTNET=true
MAX_POSITION_SIZE=0.001
MAX_LEVERAGE=5
```

### Production Conservative
```bash
LIGHTER_BASE_URL=https://mainnet.zklighter.elliot.ai
DRY_RUN=false
USE_TESTNET=false
MAX_POSITION_SIZE=0.003
MAX_LEVERAGE=5
MAX_DAILY_DRAWDOWN=0.05
```

---

## Safety Checklist

### Before First Run
- [ ] `.env` configured with valid credentials
- [ ] `USE_TESTNET=true` for initial testing
- [ ] `DRY_RUN=true` for simulation
- [ ] API connection tested successfully
- [ ] Read DEPLOYMENT_CHECKLIST.md

### Before Mainnet
- [ ] 24h testnet run completed
- [ ] All strategies validated
- [ ] Conservative position sizes set
- [ ] Emergency procedures documented
- [ ] Monitoring plan in place

---

## Strategy Toggles

```bash
# Recommended (safe)
ENABLE_MOMENTUM_STRATEGY=true
ENABLE_MEAN_REVERSION_STRATEGY=true

# Optional
ENABLE_ORDERFLOW_STRATEGY=true
ENABLE_SENTIMENT_STRATEGY=true

# Advanced (disable initially)
ENABLE_MARKET_MAKING_STRATEGY=false
ENABLE_GRID_TRADING_STRATEGY=false
```

---

## Monitoring

### Log Files
```bash
# Watch logs live
tail -f logs/bot.log

# Search for errors
grep ERROR logs/bot.log

# Check circuit breaker trips
grep "Circuit breaker OPEN" logs/bot.log
```

### Status Checks
```bash
# Bot running?
ps aux | grep "python main.py"

# Check order index
cat data/order_index.json

# Test count
pytest --collect-only | grep "test session"
```

---

## Common Issues

### "api key not found"
**Fix**: Check `LIGHTER_API_KEY_PRIVATE_KEY`, `LIGHTER_ACCOUNT_INDEX`, `LIGHTER_API_KEY_INDEX` in `.env`

### Circuit breaker constantly tripping
**Fix**: Increase `CB_FAILURE_THRESHOLD` or check network connectivity

### Orders not filling
**Fix**: Check market liquidity, consider wider slippage or market orders

### Position data mismatch
**Fix**: Restart bot to refresh state, verify market metadata

---

## Performance Targets

- **Uptime**: >99%
- **API Errors**: <5 circuit breaker trips/day
- **Tests**: 7/7 passing
- **Response Time**: <2s for order placement

---

## Resources

- **SDK**: https://github.com/elliottech/lighter-python
- **Docs**: https://docs.lighter.xyz
- **Testnet**: https://testnet.zklighter.elliot.ai
- **Mainnet**: https://mainnet.zklighter.elliot.ai

---

## Version Info

- **Bot Version**: Production-Ready v1.0
- **SDK**: lighter-python (official)
- **Python**: 3.8+
- **Last Updated**: November 11, 2025

---

**Remember**: Start testnet → Monitor 24h → Scale gradually 🚀
