#!/bin/bash

# Quick start script for Lighter Bot

set -e

echo "=========================================="
echo "Lighter Trading Bot - Quick Start"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  No .env file found!"
    echo "Copying .env.example to .env..."
    cp .env.example .env
    echo ""
    echo "Please edit .env with your API credentials:"
    echo "  nano .env"
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Create logs directory
mkdir -p logs

echo ""
echo "✓ Setup complete!"
echo ""
echo "Options:"
echo "  1) Test API connection"
echo "  2) Run utilities menu"
echo "  3) Start bot"
echo ""
read -p "Select option (1-3): " option

case $option in
    1)
        echo ""
        echo "Testing API connection..."
        python3 -c "from utils import test_api_connection; test_api_connection()"
        ;;
    2)
        echo ""
        python3 utils.py
        ;;
    3)
        echo ""
        echo "Starting Lighter Bot..."
        echo "Press Ctrl+C to stop"
        echo ""
        python3 main.py
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac
