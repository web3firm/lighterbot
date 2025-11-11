#!/bin/bash
# Quick deployment verification script

set -e

echo "=========================================="
echo "   Lighter Bot Deployment Verification"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo -n "Checking Python version... "
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
if [[ "$PYTHON_VERSION" > "3.8" ]]; then
    echo -e "${GREEN}✓${NC} $PYTHON_VERSION"
else
    echo -e "${RED}✗${NC} Python 3.8+ required"
    exit 1
fi

# Check virtual environment
echo -n "Checking virtual environment... "
if [ -d "venv" ]; then
    echo -e "${GREEN}✓${NC} Found"
else
    echo -e "${YELLOW}!${NC} Not found, creating..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Check dependencies
echo -n "Checking dependencies... "
if pip list | grep -q "lighter"; then
    echo -e "${GREEN}✓${NC} Installed"
else
    echo -e "${YELLOW}!${NC} Installing..."
    pip install -q -r requirements.txt
fi

# Check .env file
echo -n "Checking .env configuration... "
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} Found"
    
    # Check required variables
    if grep -q "LIGHTER_API_KEY_PRIVATE_KEY=replace" .env; then
        echo -e "${RED}✗${NC} ERROR: .env not configured"
        echo "   Please edit .env with your API credentials"
        exit 1
    fi
else
    echo -e "${RED}✗${NC} Missing"
    echo "   Copy .env.example to .env and configure it"
    exit 1
fi

# Check directories
echo -n "Checking directories... "
mkdir -p logs data
echo -e "${GREEN}✓${NC} Ready"

# Run tests
echo -n "Running unit tests... "
TEST_OUTPUT=$(pytest -q 2>&1)
if [ $? -eq 0 ]; then
    PASSED=$(echo "$TEST_OUTPUT" | grep -o "[0-9]* passed" | awk '{print $1}')
    echo -e "${GREEN}✓${NC} $PASSED tests passed"
else
    echo -e "${RED}✗${NC} Tests failed"
    echo "$TEST_OUTPUT"
    exit 1
fi

# Check configuration values
echo ""
echo "Configuration Summary:"
echo "======================"
source .env 2>/dev/null || true
echo "Network: $LIGHTER_BASE_URL"
echo "Testnet: $USE_TESTNET"
echo "DRY_RUN: $DRY_RUN"
echo "Market: $TRADING_SYMBOL (ID: $TRADING_MARKET_ID)"
echo "Max Position: $MAX_POSITION_SIZE"
echo "Max Leverage: ${MAX_LEVERAGE}x"
echo "Max Drawdown: $MAX_DAILY_DRAWDOWN"

echo ""
echo "=========================================="
echo -e "${GREEN}✓ All checks passed!${NC}"
echo "=========================================="
echo ""
echo "Ready to deploy. Choose an option:"
echo "  1) Test API connection"
echo "  2) Start bot (will use .env settings)"
echo "  3) Exit"
echo ""
read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo ""
        echo "Testing API connection..."
        python3 test_connection.py
        ;;
    2)
        echo ""
        if [[ "$DRY_RUN" == "true" ]]; then
            echo -e "${GREEN}🔒 DRY_RUN mode enabled - safe to test${NC}"
        else
            echo -e "${YELLOW}⚠️  WARNING: DRY_RUN=false - will place real orders!${NC}"
            read -p "Continue? (yes/no): " confirm
            if [[ "$confirm" != "yes" ]]; then
                echo "Aborted"
                exit 0
            fi
        fi
        echo ""
        echo "Starting bot... (Ctrl+C to stop)"
        ./run_bot.sh
        ;;
    3)
        echo "Exited"
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
