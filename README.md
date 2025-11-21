# 🤖 LighterBot - Automated Trading Bot for Lighter Protocol

**Enterprise-grade automated trading bot** combining rule-based strategies with machine learning for cryptocurrency futures trading on Lighter Protocol (Arbitrum DEX).

---

## ⚡ Quick Start

### **1. Clone & Install**
```bash
cd /workspaces/lighterbot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### **2. Configure**
```bash
# Copy example environment file
cp .env.example .env

# Edit with your settings
nano .env
```

Required settings:
- `LIGHTER_PRIVATE_KEY` - Your Lighter Protocol private key
- `LIGHTER_ACCOUNT_ADDRESS` - Your account address  
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID
- `DATABASE_URL` - PostgreSQL connection (optional but recommended)

### **3. Start Trading**
```bash
# Run bot
python3 app/bot.py

# Or use PM2 for production
pm2 start ecosystem.config.js
pm2 logs lighterbot
```

---

## 📊 Key Features

### **🎯 Trading Strategies**
- **Swing Trading (70%)** - Trend-following, 1-3% moves, EMA + RSI + MACD
- **Scalping (30%)** - Quick momentum, 2% target moves
- **Breakout Detection** - Volume + price action (experimental)
- **Mean Reversion** - Oversold/overbought bounces (experimental)
- **Volume Spike** - Unusual volume detection (experimental)

### **🤖 ML Two-Phase System** (V1 → V2)
- **Phase 1 (V1)**: Collects 1000+ trades to `data/trades/` directory
- **Transition**: Auto-trainer monitors trade count, triggers training at threshold
- **Phase 2 (V2)**: RandomForest model provides confidence scores for strategies
- **Auto-Retraining**: Retrains every 24 hours with new data

### **🛡️ Risk Management**
- **Kill Switch** - Auto-stops at -5% daily loss
- **Drawdown Monitor** - 10% max from peak
- **Position Limits** - Max 2 positions, 5x leverage
- **Trailing Stop-Loss** - Locks profits at 7% PnL
- **Trailing Take-Profit** - Dynamic profit protection

### **📱 Telegram Interface**
15+ commands for complete bot control:
- `/start` `/stop` - Bot control
- `/status` - Current status (shows V1/V2 phase)
- `/positions` - Open positions
- `/trades` - Recent trades
- `/pnl` - P&L summary
- `/stats` - Statistics
- `/analytics` - Performance analytics
- `/dbstats` - Database statistics
- `/train` - Force ML training
- `/help` - Command reference

### **🗄️ Database Integration** (PostgreSQL/NeonDB)
7 tables for comprehensive tracking:
- `trades` - Complete trade history
- `signals` - Strategy signals with indicators
- `ml_predictions` - ML predictions vs actual outcomes
- `positions` - Active position tracking
- `funding_payments` - Funding rate history
- `performance_metrics` - Daily/weekly statistics
- `bot_state` - Bot configuration and state

---

## 🏗️ Architecture

```
Main Loop (1s interval)
├─ Fetch Market Data (Lighter Protocol)
├─ Run All Strategies in Parallel
│  ├─ Swing Trader (70% allocation)
│  ├─ Scalping Strategy (30% allocation)
│  ├─ Breakout Strategy (experimental)
│  ├─ Mean Reversion (experimental)
│  └─ Volume Spike (experimental)
├─ ML Enhancement (if V2 active)
│  └─ Get prediction confidence for signal filtering
├─ Risk Engine Validation
│  ├─ Check daily loss limit (-5% kill switch)
│  ├─ Check position limits (max 2)
│  ├─ Check leverage limits (5x max)
│  └─ Check correlation (avoid similar positions)
├─ Execute Trade if Approved
└─ Log Trade to data/trades/ (for ML training)

Monitoring Loops (parallel)
├─ Account Updates (5s) - equity, margin, positions
├─ Position Monitoring (1s) - SL/TP tracking, trailing
├─ Risk Checks (10s) - drawdown, kill switch
├─ ML Auto-Trainer (1h) - check trade count, train if needed
└─ Telegram Notifications - real-time updates
```

---

## 📁 Project Structure

```
lighterbot/
├── app/                         # Main application
│   ├── bot.py                  # Master controller ⚠️ TODO
│   ├── telegram_bot.py         # Telegram interface ⚠️ TODO
│   ├── hl/                     # Lighter Protocol integration
│   │   ├── lighter_client.py          ⚠️ TODO
│   │   ├── lighter_order_manager.py   ⚠️ TODO
│   │   └── lighter_websocket.py       ⚠️ TODO
│   ├── strategies/             # Trading strategies
│   │   ├── strategy_manager.py        ⚠️ TODO
│   │   └── rule_based/
│   │       ├── swing_trader.py        ⚠️ TODO
│   │       ├── scalping_2pct.py       ⚠️ TODO
│   │       ├── breakout.py            ⚠️ TODO
│   │       ├── mean_reversion.py      ⚠️ TODO
│   │       └── volume_spike.py        ⚠️ TODO
│   ├── risk/                   # Risk management
│   │   ├── risk_engine.py             ⚠️ TODO
│   │   ├── kill_switch.py             ⚠️ TODO
│   │   ├── drawdown_monitor.py        ⚠️ TODO
│   │   └── risk_manager.py            ⚠️ TODO
│   ├── database/               # PostgreSQL integration
│   │   ├── db_manager.py              ⚠️ TODO
│   │   ├── schema.sql                 ⚠️ TODO
│   │   └── analytics.py               ⚠️ TODO
│   ├── execution/              # Order execution
│   │   ├── execution_engine.py        ⚠️ TODO
│   │   └── order_executor.py          ⚠️ TODO
│   ├── portfolio/              # Portfolio management
│   │   ├── account_manager.py         ⚠️ TODO
│   │   ├── portfolio_manager.py       ⚠️ TODO
│   │   └── position_manager.py        ⚠️ TODO
│   └── utils/                  # Utilities
│       ├── error_handler.py           ⚠️ TODO
│       ├── position_calculator.py     ⚠️ TODO
│       ├── symbol_manager.py          ⚠️ TODO
│       └── trading_logger.py          ⚠️ TODO
├── ml/                          # Machine learning
│   ├── auto_trainer.py         # Auto-training system ✅ COMPLETE
│   ├── training/
│   │   ├── model_trainer.py           ⚠️ TODO
│   │   ├── feature_engineering.py     ⚠️ TODO
│   │   └── dataset_builder.py         ⚠️ TODO
│   ├── inference/
│   │   └── predictor.py               ⚠️ TODO
│   └── models/                 # Trained models (generated)
├── config/                      # Configuration
│   ├── credentials.py          # Config loader ✅ COMPLETE
│   ├── trading_rules.py        # YAML loader ✅ COMPLETE
│   └── trading_rules.yml       # Parameters ✅ COMPLETE
├── data/                        # Data storage
│   ├── trades/                 # Trade logs (JSONL)
│   ├── processed/              # Processed data
│   └── model_dataset/          # ML datasets
├── logs/                        # Log files
├── .env.example                # Environment template ✅ COMPLETE
├── requirements.txt            # Dependencies ✅ COMPLETE
├── ecosystem.config.js         # PM2 config ⚠️ TODO
├── lighterbot.service          # Systemd service ⚠️ TODO
├── diagnose_vps.sh            # Diagnostics ⚠️ TODO
├── monitor.sh                  # Monitoring ⚠️ TODO
├── README.md                   # This file ✅ YOU ARE HERE
├── PRODUCTION_GUIDE.md         # Deployment guide ⚠️ TODO
├── QUICK_REFERENCE.txt         # Command reference ⚠️ TODO
└── IMPLEMENTATION_BLUEPRINT.md # Implementation plan ✅ COMPLETE
```

---

## 🔧 Configuration

### **Environment Variables** (`.env`)
```bash
# Lighter Protocol
LIGHTER_API_URL=https://api.lighter.xyz/v1
LIGHTER_PRIVATE_KEY=0x...
LIGHTER_ACCOUNT_ADDRESS=0x...
LIGHTER_TESTNET=false

# Trading
SYMBOL=BTC-USD
MAX_LEVERAGE=5
POSITION_SIZE_PCT=0.8
MAX_POSITIONS=2

# Risk
MAX_DAILY_LOSS_PCT=5.0
MAX_DRAWDOWN_PCT=10.0

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Database (optional)
DATABASE_URL=postgresql://...

# ML
ML_ENABLED=true
ML_MIN_TRADES=1000
ML_AUTO_TRAIN=true
```

### **Strategy Parameters** (`config/trading_rules.yml`)
```yaml
strategies:
  swing_trader:
    enabled: true
    allocation: 0.70        # 70% of capital
    tp_pct: 15.0           # 15% PnL target
    sl_pct: 5.0            # 5% PnL stop
    
  scalping_2pct:
    enabled: true
    allocation: 0.30        # 30% of capital
    tp_pct: 2.0            # 2% PnL target
    sl_pct: 1.0            # 1% PnL stop

risk:
  max_daily_loss_pct: 5.0
  max_drawdown_pct: 10.0
  trailing_stop_enabled: true
  trailing_stop_activation_pct: 7.0

ml:
  enabled: true
  min_trades_for_training: 1000
  auto_train: true
  retrain_interval: 86400    # 24 hours
```

---

## 📊 Implementation Status

### ✅ Complete (20%)
1. **Configuration System** (4 files)
   - Environment template
   - Credentials loader
   - Trading rules YAML
   - Configuration loader

2. **ML Auto-Training System** (1 file)
   - `ml/auto_trainer.py` (400+ lines)
   - V1 → V2 transition logic
   - RandomForest training
   - Auto-retraining

3. **Directory Structure** (29 directories)
   - Complete organization
   - All `__init__.py` files

### ⚠️ TODO (80%)
- Main bot controller (`app/bot.py`)
- Lighter Protocol integration (3 files)
- Strategy system (6 files)
- Risk management (4 files)
- Database integration (3 files)
- Telegram bot (1 file)
- Execution & portfolio (5 files)
- Utilities (4 files)
- Deployment scripts (4 files)
- Documentation (2 files)

**See [IMPLEMENTATION_BLUEPRINT.md](IMPLEMENTATION_BLUEPRINT.md) for complete implementation plan**

---

## 🎯 ML Two-Phase System (User's Primary Requirement)

### **Phase 1 (V1): Collection Mode**
```
Bot starts → Trades with strategies → Every trade logs to data/trades/
└─ Logs saved as: data/trades/trades_YYYYMMDD.jsonl
└─ Auto-trainer checks count every hour
└─ Status: "V1 (Collection)" - 500/1000 trades (50%)
```

### **Transition: Auto-Training**
```
When trade count ≥ 1000:
├─ Auto-trainer loads all trade logs
├─ Extracts features (RSI, MACD, EMA, ADX, etc.)
├─ Trains RandomForest classifier
├─ Evaluates model (accuracy, precision, recall)
├─ Saves model to ml/models/
└─ Status: "V2 (ML Active)" ✅
```

### **Phase 2 (V2): ML Prediction Mode**
```
Bot continues trading → Strategies generate signals → ML provides confidence
├─ ML predicts: "profitable" probability for each signal
├─ Strategy manager uses ML confidence to filter/boost signals
├─ Trades continue logging to data/trades/
├─ Auto-trainer retrains every 24 hours with new data
└─ Model improves over time
```

---

## 📈 Performance Targets

- **Win Rate**: 70% (target)
- **Risk-Reward**: 3:1 ratio (15% TP / 5% SL)
- **Daily Target**: +2-5% account growth
- **Max Daily Loss**: -5% (kill switch)
- **Trading Frequency**: 10-50 trades/day (varies by market)

---

## 🔐 Security

- ✅ Private keys never logged
- ✅ Tokens masked in logs
- ✅ HTTP requests sanitized
- ✅ No sensitive data in git repository
- ✅ Dedicated API wallet recommended

---

## 🚀 Deployment

### **Development**
```bash
python3 app/bot.py
```

### **Production (PM2)**
```bash
pm2 start ecosystem.config.js
pm2 logs lighterbot
pm2 monit
```

### **Production (Systemd)**
```bash
sudo cp lighterbot.service /etc/systemd/system/
sudo systemctl enable lighterbot
sudo systemctl start lighterbot
sudo systemctl status lighterbot
```

---

## 🆘 Support & Monitoring

### **Telegram Commands**
- `/status` - Check bot health and ML phase
- `/pnl` - View profit/loss
- `/positions` - See open positions
- `/train` - Force ML training

### **Logs**
```bash
# PM2 logs
pm2 logs lighterbot --lines 100

# Direct logs
tail -f logs/lighterbot_*.log
tail -f data/trades/trades_*.jsonl
```

### **Database Analytics**
```bash
# Connect to PostgreSQL
psql $DATABASE_URL

# Check trades
SELECT COUNT(*), AVG(pnl_pct) FROM trades WHERE timestamp > NOW() - INTERVAL '24 hours';

# Check ML predictions
SELECT COUNT(*), AVG(probability) FROM ml_predictions WHERE prediction = 1;
```

---

## ⚠️ Disclaimer

Trading cryptocurrencies carries substantial risk. This bot is provided for educational purposes. Use at your own risk. Never trade with capital you cannot afford to lose. Always test on testnet first.

---

## 📞 Next Steps

1. **Review** [IMPLEMENTATION_BLUEPRINT.md](IMPLEMENTATION_BLUEPRINT.md)
2. **Complete Implementation** - See blueprint for remaining 80%
3. **Test on Testnet** - Use `LIGHTER_TESTNET=true`
4. **Deploy to Production** - Start with small capital
5. **Monitor via Telegram** - Use `/status` frequently
6. **Scale Gradually** - Increase capital as confidence grows

---

**Version**: 1.0 (In Development)  
**Last Updated**: January 2025  
**License**: MIT

**⚡ Ready to complete implementation? See IMPLEMENTATION_BLUEPRINT.md! 🚀**
