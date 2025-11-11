# Bot Settings Guide

## Position Sizing

```bash
POSITION_SIZE_PERCENT=20  # % of portfolio per trade (10-30 recommended)
LEVERAGE=5                 # Leverage multiplier (1-5 recommended)
```

**Example**: $100 balance × 20% × 3x = $60 position

## Risk Management

```bash
STOP_LOSS_PERCENT=2.0  # Stop loss % (1-3 recommended)
```

## Scaled Profit Taking

```bash
# Level 1: Quick profit lock
PROFIT_LEVEL_1_PERCENT=2.0  # Price target % (1-3)
PROFIT_LEVEL_1_SIZE=30      # Position size % to exit (20-40)

# Level 2: Second profit lock
PROFIT_LEVEL_2_PERCENT=4.0  # Price target % (3-6)
PROFIT_LEVEL_2_SIZE=30      # Position size % to exit (20-40)

# Runner: Trailing portion
PROFIT_RUNNER_SIZE=40              # Remaining % (30-60)
TRAILING_STOP_ACTIVATION=4.0       # When to start trailing %
TRAILING_STOP_DISTANCE=2.0         # Trail distance % (1.5-3)
```

## Strategy Presets

### Conservative (Safe)
```bash
POSITION_SIZE_PERCENT=10
LEVERAGE=2
STOP_LOSS_PERCENT=1.5
PROFIT_LEVEL_1_PERCENT=1.5
PROFIT_LEVEL_1_SIZE=40
PROFIT_LEVEL_2_PERCENT=3.0
PROFIT_LEVEL_2_SIZE=40
PROFIT_RUNNER_SIZE=20
TRAILING_STOP_DISTANCE=1.5
```

### Balanced (Recommended)
```bash
POSITION_SIZE_PERCENT=20
LEVERAGE=3
STOP_LOSS_PERCENT=2.0
PROFIT_LEVEL_1_PERCENT=2.0
PROFIT_LEVEL_1_SIZE=30
PROFIT_LEVEL_2_PERCENT=4.0
PROFIT_LEVEL_2_SIZE=30
PROFIT_RUNNER_SIZE=40
TRAILING_STOP_DISTANCE=2.0
```

### Aggressive (Risky)
```bash
POSITION_SIZE_PERCENT=30
LEVERAGE=5
STOP_LOSS_PERCENT=3.0
PROFIT_LEVEL_1_PERCENT=3.0
PROFIT_LEVEL_1_SIZE=20
PROFIT_LEVEL_2_PERCENT=6.0
PROFIT_LEVEL_2_SIZE=20
PROFIT_RUNNER_SIZE=60
TRAILING_STOP_DISTANCE=3.0
```

## Markets

Available markets (use TRADING_MARKET_ID):
- BTC-PERP: 1
- ETH-PERP: 2
- ZEC-PERP: 90
- (Check Lighter API for full list)

## Applying Changes

1. Stop bot: `pkill -f "python main.py"`
2. Edit: `nano .env`
3. Restart: `nohup python main.py > bot.log 2>&1 &`
