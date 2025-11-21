# 🚀 Quick Start - Manual Setup

Too complicated? Just do this:

## 1. Clone the repo
```bash
git clone https://github.com/web3firm/lighterbot.git
cd lighterbot
```

## 2. Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

## 3. Install dependencies
```bash
pip install -r requirements.txt
```

## 4. Set up PostgreSQL database
```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt update && sudo apt install postgresql postgresql-contrib

# Create database
sudo -u postgres createdb lighterbot

# Initialize schema
psql postgresql://postgres@localhost/lighterbot < app/database/schema.sql
```

## 5. Configure environment
```bash
cp .env.example .env
nano .env  # Edit with your keys
```

**Required variables:**
- `DATABASE_URL` - PostgreSQL connection
- `LIGHTER_API_PRIVATE_KEY` - Your private key
- `TELEGRAM_BOT_TOKEN` - Telegram bot token
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID

## 6. Run it!
```bash
python -m app.bot
```

That's it! 🎉

---

## Keep it running (optional)

### Option 1: Screen (simplest)
```bash
screen -S lighterbot
python -m app.bot
# Press Ctrl+A then D to detach
# Re-attach: screen -r lighterbot
```

### Option 2: Nohup
```bash
nohup python -m app.bot > bot.log 2>&1 &
# Check logs: tail -f bot.log
# Stop: pkill -f "python -m app.bot"
```

### Option 3: PM2 (if you want monitoring)
```bash
# Install PM2
npm install -g pm2

# Start bot
pm2 start "python -m app.bot" --name lighterbot --interpreter python3

# View logs
pm2 logs lighterbot

# Stop
pm2 stop lighterbot
```

---

## Minimum Requirements
- Python 3.9+ (check: `python3 --version`)
- 2GB RAM
- Internet connection

## Configuration
Edit `.env` file with your credentials:
- `DATABASE_URL` - PostgreSQL connection (REQUIRED)
- `LIGHTER_API_PRIVATE_KEY` - Your Lighter Protocol private key
- `TRADING_SYMBOL` - ETH-USD (default)
- `MAX_LEVERAGE` - 5 (recommended)
- `POSITION_SIZE_PCT` - 50 (start small!)

## That's all you need! 
The complicated deployment scripts are just for automation and production setups.
