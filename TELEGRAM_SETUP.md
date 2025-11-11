# 🤖 Telegram Bot Remote Control Setup

Control your Lighter trading bot from anywhere using Telegram!

## 📋 Features

- ✅ **Start/Stop/Restart** bot remotely
- ✅ **Real-time status** monitoring
- ✅ **View logs** directly in Telegram
- ✅ **Check configuration** 
- ✅ **Interactive buttons** for easy control
- ✅ **Secure** - only you can control your bot

---

## 🚀 Quick Setup (5 minutes)

### Step 1: Create Your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` command
3. Choose a name for your bot (e.g., "My Lighter Bot")
4. Choose a username (e.g., "my_lighter_bot")
5. **Copy the bot token** you receive (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Add Token to .env

Edit your `.env` file:
```bash
nano .env
```

Add this line (replace with your actual token):
```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

Save and exit (Ctrl+X, Y, Enter)

### Step 3: Install Dependencies

```bash
./setup_telegram.sh
```

Or manually:
```bash
source venv/bin/activate
pip install python-telegram-bot psutil
```

### Step 4: Start Telegram Bot

```bash
# Start in screen (recommended)
screen -dmS telegram-bot python3 telegram_bot.py

# Or start in foreground
python3 telegram_bot.py
```

### Step 5: Use Your Bot

1. Open Telegram
2. Search for your bot username
3. Send `/start` command
4. Use the interactive buttons to control your trading bot!

---

## 📱 Available Commands

| Command | Description |
|---------|-------------|
| `/start` | Show main control panel with buttons |
| `/start_bot` | Start the trading bot |
| `/stop_bot` | Stop the trading bot |
| `/restart_bot` | Restart the trading bot |
| `/status` | Show detailed bot status |
| `/logs` | View recent log entries |
| `/config` | Display current configuration |
| `/help` | Show help message |

---

## 🎮 Control Panel

When you send `/start`, you'll see an interactive control panel with buttons:

```
┌─────────────────────────────────┐
│  🤖 Lighter Trading Bot Control │
├─────────────────────────────────┤
│  ▶️ Start Bot    ⏹️ Stop Bot    │
│  🔄 Restart      📊 Status      │
│  📝 Logs         ⚙️ Config      │
└─────────────────────────────────┘
```

---

## 🔒 Security Best Practices

### Option 1: Restrict to Your Chat (Recommended)

Get your Chat ID:
```bash
# 1. Message your bot on Telegram first
# 2. Run this script
python3 get_chat_id.py
```

Add to `.env`:
```bash
TELEGRAM_CHAT_ID=your_chat_id_here
```

Update `telegram_bot.py` to check chat ID:
```python
# Add this check in each command handler
if update.effective_chat.id != int(os.getenv('TELEGRAM_CHAT_ID', '0')):
    await update.message.reply_text("❌ Unauthorized")
    return
```

### Option 2: Use Bot Username Privacy

In BotFather:
1. Send `/mybots`
2. Select your bot
3. Go to "Bot Settings" → "Group Privacy"
4. Set to "Disable" (makes bot private)

---

## 🛠️ Advanced Usage

### Run in Background with Screen

```bash
# Start
screen -dmS telegram-bot python3 telegram_bot.py

# Attach to view
screen -r telegram-bot

# Detach (while inside screen)
Ctrl+A, then D

# List sessions
screen -ls

# Kill session
screen -X -S telegram-bot quit
```

### Run in Background with Tmux

```bash
# Start
tmux new-session -d -s telegram-bot "python3 telegram_bot.py"

# Attach to view
tmux attach -t telegram-bot

# Detach (while inside tmux)
Ctrl+B, then D

# List sessions
tmux ls

# Kill session
tmux kill-session -t telegram-bot
```

### Run as Systemd Service

Create `/etc/systemd/system/telegram-bot.service`:

```ini
[Unit]
Description=Lighter Trading Bot Telegram Controller
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/lighterbot
Environment="PATH=/root/lighterbot/venv/bin"
ExecStart=/root/lighterbot/venv/bin/python3 /root/lighterbot/telegram_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

---

## 📊 Status Display Example

When you check status, you'll see:

```
📊 Bot Status

✅ Status: RUNNING
🆔 PID: 12345
⏱️ Uptime: 5.3 hours
💾 Memory: 245.3 MB
⚙️ CPU: 2.5%

📈 Network: TESTNET
🎯 Market: BTC-PERP
🔒 DRY_RUN: true

📝 Recent Logs:
```
[INFO] Bot started successfully
[INFO] Market data updated
[INFO] Risk checks passed
```
```

---

## 🔧 Troubleshooting

### Bot Not Responding

1. Check if Telegram bot is running:
```bash
ps aux | grep telegram_bot.py
```

2. Check logs:
```bash
tail -f telegram_bot.log
```

3. Verify token in .env:
```bash
grep TELEGRAM_BOT_TOKEN .env
```

### "api key not found" Error

The bot token is invalid. Get a new one from @BotFather.

### Trading Bot Won't Start

Check main bot logs:
```bash
tail -f logs/bot.log
```

Ensure `.env` has all required settings.

### Permission Denied

Make scripts executable:
```bash
chmod +x telegram_bot.py setup_telegram.sh get_chat_id.py
```

---

## 📝 Example Workflow

### Daily Monitoring

1. **Morning**: Send `/status` to check overnight performance
2. Check `/logs` for any errors
3. Verify positions are within limits

### Making Changes

1. Send `/stop_bot` to safely stop
2. SSH to VPS and edit `.env`
3. Send `/start_bot` to restart with new config
4. Send `/status` to verify changes

### Emergency Stop

1. Open Telegram
2. Send `/stop_bot`
3. Bot stops gracefully within seconds
4. Check `/logs` to verify clean shutdown

---

## 🎯 Tips

- **Pin your bot** in Telegram for quick access
- **Set up notifications** for bot messages
- **Check status regularly** during trading hours
- **Review logs** if unexpected behavior occurs
- **Test on testnet first** before mainnet

---

## 🆘 Support

If you encounter issues:

1. Check `telegram_bot.log` for errors
2. Verify all dependencies installed: `pip list | grep telegram`
3. Test bot token: `python3 get_chat_id.py`
4. Ensure firewall allows Telegram API access

---

## 🔐 Security Checklist

- [ ] Bot token added to `.env` (not hardcoded)
- [ ] `.env` file has proper permissions (600)
- [ ] Chat ID restriction enabled (optional but recommended)
- [ ] Bot username is private/hard to guess
- [ ] VPS firewall configured properly
- [ ] Regular log review enabled

---

**Your trading bot is now controllable from anywhere! 🎉**

Stay in control of your trades with Telegram remote access.
