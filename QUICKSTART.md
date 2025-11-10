# Lighter Bot - Quick Reference Guide

## Quick Start

1. **Setup**:
   ```bash
   ./start.sh
   ```

2. **Configure** `.env` with your API credentials

3. **Test connection**:
   ```bash
   python utils.py
   # Select option 1 (Test API Connection)
   ```

4. **Start bot**:
   ```bash
   python main.py
   ```

## Essential Commands

### View Account Status
```bash
python utils.py
# Select option 2 (Display Account Status)
```

### Check Risk Metrics
```bash
python utils.py
# Select option 3 (Check Risk Status)
```

### Emergency Stop
- Press `Ctrl+C` in terminal
- Or: `kill <PID>`

### Cancel All Orders
```bash
python utils.py
# Select option 6 (Cancel All Orders)
```

### Close All Positions
```bash
python utils.py
# Select option 7 (Close All Positions)
```

## Configuration Quick Reference

### Risk Settings (.env)
- `MAX_POSITION_SIZE`: Max position in base currency (e.g., 1.0 BTC)
- `MAX_LEVERAGE`: Max leverage multiplier (e.g., 10 = 10x)
- `MAX_DAILY_DRAWDOWN`: Max daily loss (0.05 = 5%)
- `LIQUIDATION_THRESHOLD`: Liquidation risk alert level (0.8 = 80%)

### Trading Settings
- `TRADING_SYMBOL`: Symbol to trade (e.g., BTC-PERP)
- `MIN_ORDER_SIZE`: Minimum order size
- `POSITION_CHECK_INTERVAL`: Seconds between risk checks

## Strategy Management

### Enable/Disable Strategies in Code

Edit `main.py`:

```python
# Enable EMA Crossover (enabled by default)
strategy_manager.enable_strategy("EMA_Crossover_12_26")

# Enable Momentum strategy
strategy_manager.enable_strategy("Momentum_20")

# Disable a strategy
strategy_manager.disable_strategy("EMA_Crossover_12_26")
```

### Adjust Strategy Parameters

```python
# In main.py setup_strategies():
ema_strategy = EMACrossoverStrategy(
    symbol=symbol,
    market_data=self.market_data,
    order_manager=self.order_manager,
    risk_manager=self.risk_manager,
    fast_period=9,    # Faster signal (was 12)
    slow_period=21    # Faster signal (was 26)
)
```

## Monitoring

### Log Files
- `logs/bot.log` - Main log
- `logs/trades.jsonl` - All trades
- `logs/positions.jsonl` - Position updates
- `logs/errors.jsonl` - Errors

### Tail Logs
```bash
tail -f logs/bot.log
```

### View Recent Trades
```bash
tail -20 logs/trades.jsonl | jq
```

## Common Issues

### "Authentication Error"
→ Check `LIGHTER_API_KEY` and `LIGHTER_API_SECRET` in `.env`

### "Insufficient Margin"
→ Reduce `MAX_POSITION_SIZE` or `MAX_LEVERAGE`

### "Order rejected by risk manager"
→ Check risk limits in `.env`
→ Run: `python utils.py` → option 3 to see why

### Bot not trading
→ Check strategy is enabled
→ Verify symbol has liquidity
→ Check logs for errors

## Safety Checklist

- [ ] Start with testnet (`ENVIRONMENT=testnet`)
- [ ] Test with minimum size first
- [ ] Set conservative risk limits
- [ ] Monitor for first 24 hours
- [ ] Have emergency stop plan
- [ ] Understand all code before running
- [ ] Never risk more than you can lose

## Python API Examples

### Check Position
```python
from order_manager import OrderManager

om = OrderManager()
position = om.get_position("BTC-PERP")
if position:
    print(f"Size: {position.size}")
    print(f"PnL: {position.unrealized_pnl}")
```

### Place Order
```python
from order_manager import OrderManager

om = OrderManager()
order = om.place_limit_order(
    symbol="BTC-PERP",
    side="buy",
    size=0.1,
    price=50000
)
```

### Get Market Price
```python
from market_data import MarketData

md = MarketData()
price = md.get_current_price("BTC-PERP")
print(f"Price: ${price}")
```

## Support Resources

- **Lighter Docs**: https://docs.lighter.xyz/
- **API Docs**: https://docs.lighter.xyz/perpetual-futures/sub-accounts-and-api-keys
- **Funding**: https://docs.lighter.xyz/perpetual-futures/funding

## Emergency Contacts

If bot malfunctions:
1. Press `Ctrl+C` to stop
2. Run `python utils.py` → option 6 (cancel orders)
3. Run `python utils.py` → option 7 (close positions)
4. Check logs in `logs/` directory
