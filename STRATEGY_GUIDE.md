# Trading Strategy Guide

## Overview

Your Lighter bot now uses **6 advanced strategies** that can be enabled/disabled independently:

1. ✅ **Momentum Strategy** (Technical)
2. ✅ **Mean Reversion Strategy** (Technical)
3. ⚪ **Market Making Strategy** (Technical) - Disabled by default
4. ⚪ **Grid Trading Strategy** (Technical) - Disabled by default
5. ✅ **Order Flow Strategy** (Market Microstructure) - **NEW!**
6. ✅ **Sentiment Strategy** (News & Social) - **NEW!**

---

## 🆕 Order Flow Strategy

**What it analyzes:**
- **Order book imbalance**: Compares bid volume vs ask volume
- **Whale detection**: Identifies large orders (>3x average)
- **Trade flow**: Measures aggressive buyers vs sellers in recent trades

**Data source:**
- Lighter API: `order_books()` and `recent_trades()`
- 100% on-chain data, no external APIs needed

**Signals:**
- **Bullish**: High bid pressure, whale buy walls, aggressive buying
- **Bearish**: High ask pressure, whale sell walls, aggressive selling
- **Threshold**: Minimum 0.6 strength to trigger

**Configuration:**
```env
ENABLE_ORDERFLOW_STRATEGY=true
```

**Example signal:**
```
Order Flow: Strong bid pressure detected (imbalance=0.75)
- Bid volume: 15.3 BTC
- Ask volume: 4.2 BTC
- Whale orders: 2 large buy walls detected
- Recent trades: 70% aggressive buyers
```

---

## 🆕 Sentiment Strategy

**What it analyzes:**
- **Fear & Greed Index**: Market-wide sentiment (0-100)
  - 0-25: Extreme Fear → Bullish signal (buy the fear)
  - 75-100: Extreme Greed → Bearish signal (sell the greed)
- **News sentiment**: Positive/negative keyword analysis
- **CoinGecko sentiment**: Community voting data
- **Social metrics**: Twitter followers, price trends

**Data sources:**
- Fear & Greed Index: https://api.alternative.me/fng/
- CryptoCompare News: https://min-api.cryptocompare.com/data/v2/news/
- CoinGecko API: https://api.coingecko.com/api/v3/coins/

**Signals:**
- **Bullish**: Positive sentiment across multiple sources
- **Bearish**: Negative sentiment across multiple sources
- **Threshold**: Minimum 0.6 confidence to trigger
- **Note**: Sentiment signals are weighted at 70% (longer-term signals)

**Configuration:**
```env
ENABLE_SENTIMENT_STRATEGY=true
```

**Example signal:**
```
Sentiment: Positive market sentiment across multiple sources (score=0.65)
- Fear & Greed: 25 (Extreme Fear)
- News: 8/2 positive/negative mentions
- Community: 72% bullish
```

---

## Strategy Consensus Mechanism

All enabled strategies vote on each trading decision:

```
Buy Signal Generated:
├─ Momentum Strategy: BUY (strength: 0.75)
├─ Mean Reversion Strategy: HOLD (strength: 0.40)
├─ Order Flow Strategy: BUY (strength: 0.82)
└─ Sentiment Strategy: BUY (strength: 0.60)

Consensus: BUY (3/4 strategies agree, combined strength: 0.72)
```

**Execution rules:**
- Minimum 50% strategy agreement required
- Combined strength must exceed 0.5
- Risk manager validates position size (Kelly Criterion)
- Auto stop-loss at -2%, take-profit at +4%

---

## Enabling/Disabling Strategies

Edit `.env` file:

```env
# Technical Strategies
ENABLE_MOMENTUM_STRATEGY=true          # RSI + MACD + EMA
ENABLE_MEAN_REVERSION_STRATEGY=true    # Bollinger Bands + RSI
ENABLE_MARKET_MAKING_STRATEGY=false    # Spread capture (requires liquidity)
ENABLE_GRID_TRADING_STRATEGY=false     # Range-bound markets

# Advanced Strategies
ENABLE_ORDERFLOW_STRATEGY=true         # Order book analysis
ENABLE_SENTIMENT_STRATEGY=true         # News & social media
```

**Recommended combinations:**

### Conservative (Currently Active)
```
Momentum + Mean Reversion + Order Flow + Sentiment
```
- Multiple confirmations required
- Balanced technical + fundamental approach
- Good for trending markets with occasional reversions

### Aggressive (More trades)
```
Momentum + Order Flow
```
- Faster signals
- Rides strong trends
- Higher risk/reward

### Range-Bound Markets
```
Mean Reversion + Grid Trading
```
- Profits from sideways movement
- Requires stable price range

---

## Signal Strength Thresholds

Each strategy generates signals with strength 0.0 to 1.0:

| Strength | Meaning | Action |
|----------|---------|--------|
| 0.0-0.5 | Weak signal | Ignored |
| 0.5-0.6 | Moderate | Considered in consensus |
| 0.6-0.8 | Strong | High priority |
| 0.8-1.0 | Very strong | Maximum confidence |

---

## Order Flow Metrics Explained

**Bid/Ask Imbalance:**
```
Ratio = Bid Volume / Ask Volume

> 1.5: Strong buying pressure (bullish)
< 0.67: Strong selling pressure (bearish)
```

**Whale Detection:**
```
Large order = Order size > 3x average order size

Detected in top 10 levels of order book
Indicates institutional activity
```

**Trade Flow:**
```
Aggressive buyers = Market buy orders (takers)
Aggressive sellers = Market sell orders (takers)

> 60% aggressive buyers: Bullish momentum
> 60% aggressive sellers: Bearish momentum
```

---

## Sentiment Scoring

**Combined sentiment score (-1.0 to +1.0):**

```python
Weights:
- Fear & Greed Index: 1.5x (inverted - fear is bullish)
- News sentiment: 1.0x
- CoinGecko sentiment: 0.8x

Example:
Fear & Greed = 20 (Extreme Fear) → +0.6 (bullish)
News = 8 positive, 2 negative → +0.6 (bullish)
CoinGecko = 68% bullish → +0.36 (bullish)

Combined = (0.6*1.5 + 0.6*1.0 + 0.36*0.8) / 3.3 = 0.62
→ Bullish signal with 0.62 confidence
```

---

## Testing New Strategies

**Check what strategies are running:**
```bash
python main.py
# Look for initialization logs:
# ✓ Enabled: Momentum Strategy
# ✓ Enabled: Order Flow Strategy
# ✓ Enabled: Sentiment Strategy
```

**Monitor strategy signals:**
```bash
tail -f logs/bot.log | grep "Strategy"
```

You'll see:
```
[2024-01-15 10:30:45] Strategy signals: [
  Momentum: BUY (0.75),
  OrderFlow: BUY (0.82),
  Sentiment: NEUTRAL (0.45)
]
[2024-01-15 10:30:45] Consensus: BUY (strength: 0.79)
```

---

## API Rate Limits

**Order Flow Strategy:**
- No external APIs (uses Lighter directly)
- Rate limit: Same as your Lighter API limit

**Sentiment Strategy:**
- Fear & Greed: No rate limit
- CryptoCompare: ~1 req/sec (free tier)
- CoinGecko: 10-50 req/min (free tier)
- Cache duration: 5 minutes (automatic)

**Note:** All sentiment data is cached for 5 minutes to avoid excessive API calls.

---

## Performance Monitoring

Track which strategies are most profitable:

```python
# Check logs/bot.log for:
[2024-01-15] Trade executed: BUY 0.002 BTC @ $45,000
  Triggered by: OrderFlow Strategy (0.82)
  Supporting: Momentum (0.75), Sentiment (0.60)
  
[2024-01-15] Position closed: +$25.50 profit
  Entry: OrderFlow signal
  Exit: Auto take-profit (+4%)
```

Your risk manager tracks win rate per strategy type over time.

---

## Troubleshooting

**Order Flow Strategy not triggering:**
- Check if there's enough order book depth
- Increase lookback_trades parameter (currently 50)
- Lower strength threshold in code (currently 0.6)

**Sentiment Strategy showing neutral:**
- Market might genuinely be neutral
- Check API availability: `curl https://api.alternative.me/fng/`
- Verify cache isn't stale (check timestamps in logs)

**Too many/too few trades:**
- Adjust number of enabled strategies
- Modify consensus threshold (currently 50%)
- Change signal strength thresholds

---

## Next Steps

1. **Run the bot**: `python main.py`
2. **Monitor for 1 hour**: Watch how strategies vote
3. **Adjust thresholds**: Based on signal frequency
4. **Disable underperforming strategies**: Check win rates
5. **Fine-tune**: Modify weights and thresholds in code

Your bot now combines:
- ✅ Technical indicators (price patterns)
- ✅ Order flow analysis (institutional activity)
- ✅ Sentiment analysis (market psychology)

This is a **multi-dimensional trading system** similar to what institutional traders use!
