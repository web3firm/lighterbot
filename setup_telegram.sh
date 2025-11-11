#!/bin/bash
# Setup script for Telegram Bot integration

set -e

echo "=========================================="
echo "   Telegram Bot Setup for Lighter Bot"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing Telegram bot dependencies..."
pip install -q python-telegram-bot>=20.7 psutil>=5.9.0

echo ""
echo "✅ Dependencies installed!"
echo ""
echo "=========================================="
echo "   Get Your Telegram Bot Token"
echo "=========================================="
echo ""
echo "1. Open Telegram and search for @BotFather"
echo "2. Send /newbot command"
echo "3. Follow instructions to create your bot"
echo "4. Copy the bot token you receive"
echo "5. Add it to your .env file:"
echo ""
echo "   TELEGRAM_BOT_TOKEN=your_token_here"
echo ""
echo "6. (Optional) Get your chat ID:"
echo "   - Message your bot on Telegram"
echo "   - Run: python3 get_chat_id.py"
echo "   - Add to .env: TELEGRAM_CHAT_ID=your_chat_id"
echo ""
echo "=========================================="
echo ""

read -p "Have you added TELEGRAM_BOT_TOKEN to .env? (y/n): " confirm

if [[ "$confirm" != "y" ]]; then
    echo ""
    echo "Please edit .env and add your Telegram token:"
    echo "  nano .env"
    echo ""
    echo "Then run this script again or start the bot directly:"
    echo "  python3 telegram_bot.py"
    exit 0
fi

echo ""
echo "=========================================="
echo "   Starting Telegram Bot Controller"
echo "=========================================="
echo ""
echo "The bot will run in the background."
echo "You can control it from Telegram!"
echo ""
echo "Commands:"
echo "  • /start - Main control panel"
echo "  • /status - Check bot status"
echo "  • /start_bot - Start trading bot"
echo "  • /stop_bot - Stop trading bot"
echo "  • /logs - View recent logs"
echo ""

# Start in background with screen or tmux if available
if command -v screen &> /dev/null; then
    screen -dmS telegram-bot python3 telegram_bot.py
    echo "✅ Telegram bot started in screen session 'telegram-bot'"
    echo ""
    echo "To attach: screen -r telegram-bot"
    echo "To detach: Ctrl+A, then D"
elif command -v tmux &> /dev/null; then
    tmux new-session -d -s telegram-bot "python3 telegram_bot.py"
    echo "✅ Telegram bot started in tmux session 'telegram-bot'"
    echo ""
    echo "To attach: tmux attach -t telegram-bot"
    echo "To detach: Ctrl+B, then D"
else
    # Run in background with nohup
    nohup python3 telegram_bot.py > telegram_bot.log 2>&1 &
    echo "✅ Telegram bot started in background (PID: $!)"
    echo "Logs: telegram_bot.log"
fi

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Open Telegram and send /start to your bot!"
echo ""
