#!/bin/bash
# Start the Lighter trading bot

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Run the bot
python main.py
