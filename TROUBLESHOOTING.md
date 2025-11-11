# Troubleshooting

## No Trades Happening

**Reason**: Confidence below 65% threshold (bot protecting capital)

**Check**:
```bash
tail -f bot.log | grep confidence
```

**Solutions**:
- Wait for better market conditions (recommended)
- Market is ranging/choppy - bot correctly waiting
- This is a feature, not a bug!

## Position Size Too Small

**Error**: "Position size below minimum"

**Fix**: Increase position size
```bash
# In .env:
POSITION_SIZE_PERCENT=25  # Increase from 20
LEVERAGE=4                 # Increase from 3
```

## Bot Stopped

**Check if running**:
```bash
ps aux | grep "python main.py"
```

**Restart**:
```bash
cd /root/lighterbot
source venv/bin/activate
nohup python main.py > bot.log 2>&1 &
```

## Errors in Logs

**Check recent errors**:
```bash
tail -100 bot.log | grep ERROR
```

**Common fixes**:
- API keys invalid: Check `.env` credentials
- Network issues: Wait and restart
- Daily drawdown hit: Bot auto-stopped (safety feature)

## Balance Shows Zero

**Check account**:
```bash
grep "collateral" bot.log | tail -5
```

**Possible causes**:
- Wrong account index
- No funds in account
- API connection issue

## Want More Trades

Current: 65% confidence threshold (high win rate)

**Option 1**: Wait (recommended) - quality over quantity

**Option 2**: Lower threshold (reduces win rate)
- Edit `win_rate_optimizer.py` line ~477
- Change `0.65` to `0.55` (accept FAIR setups)
- Not recommended unless you understand implications

## Connection Issues

**Test API**:
```bash
curl https://mainnet.zklighter.elliot.ai/health
```

**Check bot logs**:
```bash
tail -50 bot.log | grep -E "ERROR|WARNING"
```

## Performance Questions

**View trade history**:
```bash
cat trade_history.json
```

**Check metrics**:
```
http://localhost:9090/metrics
```

**Calculate win rate**:
```bash
grep "win_rate" bot.log | tail -5
```

## Getting Help

1. Check logs: `tail -100 bot.log`
2. Check settings: `cat .env`
3. Verify bot running: `ps aux | grep python`
4. Check balance: `grep collateral bot.log | tail -1`
