#!/bin/bash

################################################################################
# LighterBot VPS Deployment Script
# Automated deployment for Ubuntu 20.04+ VPS
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/opt/lighterbot"
SERVICE_NAME="lighterbot"
LOG_DIR="/var/log/lighterbot"
PYTHON_VERSION=""  # Auto-detect

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "\n${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  $1"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then 
        print_error "Please run as root or with sudo"
        exit 1
    fi
}

################################################################################
# System Checks
################################################################################

system_checks() {
    print_header "Running System Checks"
    
    # Check OS
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        print_info "OS: $NAME $VERSION"
    else
        print_error "Cannot determine OS version"
        exit 1
    fi
    
    # Check architecture
    ARCH=$(uname -m)
    print_info "Architecture: $ARCH"
    
    # Check available disk space (need at least 5GB)
    AVAILABLE_SPACE=$(df / | tail -1 | awk '{print $4}')
    if [ $AVAILABLE_SPACE -lt 5242880 ]; then
        print_warning "Low disk space. Recommend at least 5GB free."
    fi
    
    # Check RAM (recommend at least 2GB)
    TOTAL_RAM=$(free -m | awk '/^Mem:/{print $2}')
    print_info "RAM: ${TOTAL_RAM}MB"
    if [ $TOTAL_RAM -lt 2000 ]; then
        print_warning "Low RAM. Recommend at least 2GB for stable operation."
    fi
    
    print_success "System checks completed"
}

################################################################################
# Install Dependencies
################################################################################

install_dependencies() {
    print_header "Installing System Dependencies"
    
    # Update package list
    print_info "Updating package list..."
    apt-get update -qq
    
    # Detect available Python version (prefer 3.11, 3.10, 3.9, fallback to python3)
    print_info "Detecting Python version..."
    if command -v python3.11 >/dev/null 2>&1 || apt-cache show python3.11 >/dev/null 2>&1; then
        PYTHON_VERSION="3.11"
    elif command -v python3.10 >/dev/null 2>&1 || apt-cache show python3.10 >/dev/null 2>&1; then
        PYTHON_VERSION="3.10"
    elif command -v python3.9 >/dev/null 2>&1 || apt-cache show python3.9 >/dev/null 2>&1; then
        PYTHON_VERSION="3.9"
    else
        PYTHON_VERSION="3"
    fi
    print_info "Using Python ${PYTHON_VERSION}"
    
    # Install Python and development tools
    print_info "Installing Python packages..."
    if [ "$PYTHON_VERSION" = "3" ]; then
        # Fallback to generic python3 packages
        apt-get install -y python3 python3-venv python3-dev python3-pip 2>/dev/null || \
        apt-get install -y python3 python3.10-venv python3-dev python3-pip 2>/dev/null || \
        apt-get install -y python3 python3-pip
    else
        # Try versioned packages first, fall back to generic if they don't exist
        apt-get install -y python${PYTHON_VERSION} 2>/dev/null || true
        apt-get install -y python${PYTHON_VERSION}-venv 2>/dev/null || apt-get install -y python3-venv 2>/dev/null || true
        apt-get install -y python${PYTHON_VERSION}-dev 2>/dev/null || apt-get install -y python3-dev 2>/dev/null || true
        apt-get install -y python3-pip 2>/dev/null || true
    fi
    
    # Verify Python installation
    if ! command -v python3 >/dev/null 2>&1; then
        print_error "Python3 installation failed"
        exit 1
    fi
    
    INSTALLED_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    print_success "Python ${INSTALLED_VERSION} installed successfully"
    
    # Install pip if not available
    if ! command -v pip3 >/dev/null 2>&1; then
        print_info "Installing pip..."
        curl -sSL https://bootstrap.pypa.io/get-pip.py | python3
    fi
    
    # Install other required packages
    print_info "Installing system packages..."
    apt-get install -y \
        git \
        curl \
        build-essential \
        libssl-dev \
        libffi-dev \
        supervisor \
        nginx \
        ufw \
        fail2ban \
        logrotate \
        htop \
        net-tools \
        postgresql-client 2>/dev/null || true
    
    print_success "System dependencies installed"
}

################################################################################
# Create User
################################################################################

create_app_user() {
    print_header "Creating Application User"
    
    if id -u lighterbot >/dev/null 2>&1; then
        print_info "User 'lighterbot' already exists"
    else
        useradd -r -m -d /home/lighterbot -s /bin/bash lighterbot
        print_success "User 'lighterbot' created"
    fi
}

################################################################################
# Setup Application Directory
################################################################################

setup_app_directory() {
    print_header "Setting Up Application Directory"
    
    # Create directories
    mkdir -p $APP_DIR
    mkdir -p $LOG_DIR
    mkdir -p $APP_DIR/logs
    mkdir -p $APP_DIR/data
    mkdir -p $APP_DIR/data/trades
    mkdir -p $APP_DIR/data/model_dataset
    
    # Clone or update repository
    if [ -d "$APP_DIR/.git" ]; then
        print_info "Updating existing repository..."
        cd $APP_DIR
        sudo -u lighterbot git pull
    else
        print_info "Cloning repository..."
        read -p "Enter GitHub repository URL: " REPO_URL
        git clone $REPO_URL $APP_DIR
    fi
    
    # Set permissions
    chown -R lighterbot:lighterbot $APP_DIR
    chown -R lighterbot:lighterbot $LOG_DIR
    chmod 750 $APP_DIR
    
    print_success "Application directory setup completed"
}

################################################################################
# Setup Python Environment
################################################################################

setup_python_env() {
    print_header "Setting Up Python Virtual Environment"
    
    cd $APP_DIR
    
    # Determine Python command
    if [ "$PYTHON_VERSION" = "3" ]; then
        PYTHON_CMD="python3"
    else
        PYTHON_CMD="python${PYTHON_VERSION}"
    fi
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        print_info "Creating virtual environment with $PYTHON_CMD..."
        sudo -u lighterbot $PYTHON_CMD -m venv venv
    else
        print_info "Virtual environment already exists"
    fi
    
    # Install dependencies
    print_info "Installing Python dependencies..."
    sudo -u lighterbot bash -c "source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"
    
    print_success "Python environment setup completed"
}

################################################################################
# Configure Environment Variables
################################################################################

configure_env() {
    print_header "Configuring Environment Variables"
    
    if [ -f "$APP_DIR/.env" ]; then
        print_warning ".env file already exists"
        read -p "Do you want to reconfigure? (y/N): " RECONFIGURE
        if [ "$RECONFIGURE" != "y" ] && [ "$RECONFIGURE" != "Y" ]; then
            print_info "Skipping environment configuration"
            return
        fi
    fi
    
    print_info "Please provide the following credentials:"
    
    # Lighter Protocol credentials
    read -p "Lighter API URL (default: https://mainnet.zklighter.elliot.ai): " LIGHTER_API_URL
    LIGHTER_API_URL=${LIGHTER_API_URL:-https://mainnet.zklighter.elliot.ai}
    
    read -sp "Lighter API Private Key: " LIGHTER_API_PRIVATE_KEY
    echo
    
    read -p "Lighter API Key Index (default: 0): " LIGHTER_API_KEY_INDEX
    LIGHTER_API_KEY_INDEX=${LIGHTER_API_KEY_INDEX:-0}
    
    read -p "Lighter Account Index (default: 0): " LIGHTER_ACCOUNT_INDEX
    LIGHTER_ACCOUNT_INDEX=${LIGHTER_ACCOUNT_INDEX:-0}
    
    read -p "Lighter Market ID (0=ETH-USD): " LIGHTER_MARKET_ID
    LIGHTER_MARKET_ID=${LIGHTER_MARKET_ID:-0}
    
    # Trading configuration
    read -p "Trading Symbol (default: ETH-USD): " TRADING_SYMBOL
    TRADING_SYMBOL=${TRADING_SYMBOL:-ETH-USD}
    
    read -p "Max Leverage (1-50, default: 5): " MAX_LEVERAGE
    MAX_LEVERAGE=${MAX_LEVERAGE:-5}
    
    read -p "Position Size % (1-100, default: 50): " POSITION_SIZE_PCT
    POSITION_SIZE_PCT=${POSITION_SIZE_PCT:-50}
    
    read -p "Take Profit % (default: 15): " TP_PNL_PCT
    TP_PNL_PCT=${TP_PNL_PCT:-15}
    
    read -p "Stop Loss % (default: 5): " SL_PNL_PCT
    SL_PNL_PCT=${SL_PNL_PCT:-5}
    
    read -p "Max Daily Loss % (default: 10): " MAX_DAILY_LOSS_PCT
    MAX_DAILY_LOSS_PCT=${MAX_DAILY_LOSS_PCT:-10}
    
    # Optional Telegram
    read -p "Enable Telegram notifications? (y/N): " ENABLE_TELEGRAM
    if [ "$ENABLE_TELEGRAM" = "y" ] || [ "$ENABLE_TELEGRAM" = "Y" ]; then
        read -p "Telegram Bot Token: " TELEGRAM_BOT_TOKEN
        read -p "Telegram Chat ID: " TELEGRAM_CHAT_ID
        TELEGRAM_ENABLED="true"
    else
        TELEGRAM_BOT_TOKEN=""
        TELEGRAM_CHAT_ID=""
        TELEGRAM_ENABLED="false"
    fi
    
    # Create .env file
    cat > $APP_DIR/.env << EOF
# Lighter Protocol Configuration
LIGHTER_API_URL=$LIGHTER_API_URL
LIGHTER_API_PRIVATE_KEY=$LIGHTER_API_PRIVATE_KEY
LIGHTER_API_KEY_INDEX=$LIGHTER_API_KEY_INDEX
LIGHTER_ACCOUNT_INDEX=$LIGHTER_ACCOUNT_INDEX
LIGHTER_MARKET_ID=$LIGHTER_MARKET_ID

# Trading Configuration
TRADING_SYMBOL=$TRADING_SYMBOL
MAX_LEVERAGE=$MAX_LEVERAGE
POSITION_SIZE_PCT=$POSITION_SIZE_PCT
TP_PNL_PCT=$TP_PNL_PCT
SL_PNL_PCT=$SL_PNL_PCT
MAX_DAILY_LOSS_PCT=$MAX_DAILY_LOSS_PCT
MAX_OPEN_POSITIONS=1
POSITION_COOLDOWN_SECONDS=30

# Strategy Configuration
SCALPING_ALLOCATION=30
SWING_ALLOCATION=70
MIN_MOMENTUM_PCT=0.3
MIN_SIGNAL_CONFIDENCE=0.7

# Technical Indicators
RSI_PERIOD=14
EMA_FAST=21
EMA_SLOW=50
MACD_FAST=12
MACD_SLOW=26
MACD_SIGNAL=9
ADX_PERIOD=14
BB_PERIOD=20

# Risk Management
MAX_DRAWDOWN_PCT=15.0
DRAWDOWN_WARNING_PCT=5.0

# Trailing Stop (Optional)
TRAILING_SL_ENABLED=false
TRAILING_SL_TRAIL_PCT=2.0
TRAILING_SL_CALLBACK_PCT=0.5
TRAILING_SL_ACTIVATION_PCT=1.0

# Telegram Notifications
TELEGRAM_NOTIFICATIONS_ENABLED=$TELEGRAM_ENABLED
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID

# Database (Optional)
# DATABASE_URL=postgresql://user:pass@localhost/lighterbot

# ML Training
ML_TRAINING_ENABLED=true
ML_MIN_SAMPLES=100
ML_RETRAIN_INTERVAL_HOURS=24
EOF
    
    # Secure .env file
    chown lighterbot:lighterbot $APP_DIR/.env
    chmod 600 $APP_DIR/.env
    
    print_success "Environment configuration completed"
}

################################################################################
# Setup Systemd Service
################################################################################

setup_systemd_service() {
    print_header "Setting Up Systemd Service"
    
    cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=LighterBot Trading Bot
After=network.target

[Service]
Type=simple
User=lighterbot
Group=lighterbot
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/python -m app.bot
Restart=always
RestartSec=10
StandardOutput=append:$LOG_DIR/bot.log
StandardError=append:$LOG_DIR/error.log

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP_DIR/logs $APP_DIR/data $LOG_DIR

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable ${SERVICE_NAME}
    
    print_success "Systemd service created and enabled"
}

################################################################################
# Setup Log Rotation
################################################################################

setup_logrotate() {
    print_header "Setting Up Log Rotation"
    
    cat > /etc/logrotate.d/lighterbot << EOF
$LOG_DIR/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    copytruncate
    create 0640 lighterbot lighterbot
}

$APP_DIR/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    copytruncate
    create 0640 lighterbot lighterbot
}
EOF
    
    print_success "Log rotation configured"
}

################################################################################
# Setup Firewall
################################################################################

setup_firewall() {
    print_header "Configuring Firewall"
    
    print_info "Enabling UFW firewall..."
    
    # Allow SSH
    ufw allow OpenSSH
    
    # Allow HTTPS (for API access)
    ufw allow 443/tcp
    
    # Enable firewall
    echo "y" | ufw enable
    
    print_success "Firewall configured"
}

################################################################################
# Setup Monitoring
################################################################################

setup_monitoring() {
    print_header "Setting Up Monitoring Script"
    
    cat > $APP_DIR/monitor.sh << 'EOF'
#!/bin/bash
# LighterBot Health Check Script

SERVICE_NAME="lighterbot"
LOG_FILE="/var/log/lighterbot/monitor.log"

check_service() {
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "$(date): Service is running" >> $LOG_FILE
        return 0
    else
        echo "$(date): Service is down, attempting restart..." >> $LOG_FILE
        systemctl restart $SERVICE_NAME
        sleep 5
        if systemctl is-active --quiet $SERVICE_NAME; then
            echo "$(date): Service restarted successfully" >> $LOG_FILE
        else
            echo "$(date): Service restart failed" >> $LOG_FILE
        fi
        return 1
    fi
}

check_disk_space() {
    USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ $USAGE -gt 90 ]; then
        echo "$(date): WARNING - Disk usage is at ${USAGE}%" >> $LOG_FILE
    fi
}

check_memory() {
    USAGE=$(free | grep Mem | awk '{print int($3/$2 * 100)}')
    if [ $USAGE -gt 90 ]; then
        echo "$(date): WARNING - Memory usage is at ${USAGE}%" >> $LOG_FILE
    fi
}

check_service
check_disk_space
check_memory
EOF
    
    chmod +x $APP_DIR/monitor.sh
    
    # Add to crontab for lighterbot user
    (crontab -u lighterbot -l 2>/dev/null; echo "*/5 * * * * $APP_DIR/monitor.sh") | crontab -u lighterbot -
    
    print_success "Monitoring script installed (runs every 5 minutes)"
}

################################################################################
# Main Installation
################################################################################

main() {
    print_header "LighterBot VPS Deployment"
    
    check_root
    
    print_info "This script will install and configure LighterBot on your VPS"
    read -p "Continue with installation? (y/N): " CONTINUE
    
    if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
        print_info "Installation cancelled"
        exit 0
    fi
    
    system_checks
    install_dependencies
    create_app_user
    setup_app_directory
    setup_python_env
    configure_env
    setup_systemd_service
    setup_logrotate
    setup_firewall
    setup_monitoring
    
    print_header "Installation Complete!"
    
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    🎉 Success!                               ║"
    echo "║         LighterBot has been installed successfully          ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "\n${BLUE}Next Steps:${NC}"
    echo "1. Start the bot:"
    echo "   ${YELLOW}sudo systemctl start lighterbot${NC}"
    echo ""
    echo "2. Check status:"
    echo "   ${YELLOW}sudo systemctl status lighterbot${NC}"
    echo ""
    echo "3. View logs:"
    echo "   ${YELLOW}sudo journalctl -u lighterbot -f${NC}"
    echo "   ${YELLOW}tail -f /var/log/lighterbot/bot.log${NC}"
    echo ""
    echo "4. Stop the bot:"
    echo "   ${YELLOW}sudo systemctl stop lighterbot${NC}"
    echo ""
    echo "5. Restart the bot:"
    echo "   ${YELLOW}sudo systemctl restart lighterbot${NC}"
    echo ""
    
    print_info "Bot will automatically start on system reboot"
    print_info "Health checks run every 5 minutes via cron"
    print_info "Logs are rotated daily and kept for 30 days"
    
    echo -e "\n${YELLOW}⚠️  Important:${NC}"
    echo "- Your .env file is located at: $APP_DIR/.env"
    echo "- Keep your private keys secure"
    echo "- Monitor logs regularly for errors"
    echo "- Test with small position sizes first"
    
    echo -e "\n${GREEN}Happy trading! 🚀${NC}\n"
}

# Run main installation
main
