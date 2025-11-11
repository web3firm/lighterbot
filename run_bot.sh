#!/bin/bash
# Start the Lighter trading bot
set -euo pipefail

cd "$(dirname "$0")"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "Please create .env from .env.example and configure your credentials"
    exit 1
fi

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/.installed" ]; then
    echo "Installing dependencies..."
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    touch venv/.installed
fi

# Create necessary directories
mkdir -p logs data

echo "🚀 Starting Lighter Trading Bot..."
echo "📊 Check logs/bot.log for detailed output"
echo "⏹️  Press Ctrl+C to stop"
echo ""

# Run the bot
python3 main.py
