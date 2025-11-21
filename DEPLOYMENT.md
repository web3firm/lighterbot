# LighterBot Deployment Guide

## Enterprise-Grade Deployment for Production Trading

---

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Security Hardening](#security-hardening)
6. [Deployment Options](#deployment-options)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Hardware Requirements
- **CPU**: 2+ cores (4+ recommended for ML training)
- **RAM**: 2GB minimum (4GB+ recommended)
- **Storage**: 10GB minimum (SSD recommended)
- **Network**: Stable internet connection with <100ms latency to exchange

### Software Requirements
- **Python**: 3.9 or higher
- **OS**: Linux (Ubuntu 20.04+), macOS, or Windows with WSL2
- **Database** (optional): PostgreSQL 12+
- **Dependencies**: See `requirements.txt`

### Network Requirements
- Outbound HTTPS access to Lighter Protocol APIs
- WebSocket support for real-time data
- Optional: Telegram API access for notifications

---

## Pre-Deployment Checklist

### ✅ Security
- [ ] Private keys stored securely (never commit to git)
- [ ] Environment variables configured in `.env` file
- [ ] Database credentials use strong passwords
- [ ] Telegram bot token secured
- [ ] API endpoints use HTTPS only
- [ ] Log files exclude sensitive data

### ✅ Configuration
- [ ] Trading parameters reviewed and tested
- [ ] Risk limits configured (max drawdown, daily loss)
- [ ] Position sizing calculated for account size
- [ ] Leverage settings appropriate for strategy
- [ ] Kill switch thresholds verified

### ✅ Testing
- [ ] Bot tested on testnet environment
- [ ] All API connections verified
- [ ] Order placement tested (small sizes)
- [ ] Risk management validated
- [ ] Telegram notifications working

---

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/lighterbot.git
cd lighterbot
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Verify Installation
```bash
python -c "import lighter; print(f'Lighter SDK v{lighter.__version__}')"
```

Expected output: `Lighter SDK v1.0.0` or higher

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Copy example configuration
cp .env.example .env
```

### Required Configuration

```bash
# =============================================================================
# LIGHTER PROTOCOL CONFIGURATION
# =============================================================================
LIGHTER_API_URL=https://mainnet.zklighter.elliot.ai  # Use testnet for testing
LIGHTER_API_PRIVATE_KEY=your_private_key_here
LIGHTER_ACCOUNT_INDEX=0
LIGHTER_API_KEY_INDEX=0
LIGHTER_MARKET_ID=0  # 0=ETH-USD, check docs for other markets

# =============================================================================
# TRADING CONFIGURATION
# =============================================================================
TRADING_SYMBOL=ETH-USD
BOT_MODE=rule_based  # Options: rule_based, ml_based
MAX_LEVERAGE=5
POSITION_SIZE_PCT=80.0  # Use 80% of available balance per trade
MAX_POSITIONS=1
STOP_LOSS_PCT=5.0  # 5% stop loss
TAKE_PROFIT_PCT=15.0  # 15% take profit

# =============================================================================
# RISK MANAGEMENT
# =============================================================================
MAX_DAILY_LOSS_PCT=5.0  # Stop trading if daily loss exceeds 5%
MAX_DRAWDOWN_PCT=10.0  # Kill switch at 10% drawdown
MAX_POSITION_SIZE_PCT=70.0  # Never use more than 70% of equity

# =============================================================================
# TELEGRAM NOTIFICATIONS (Optional)
# =============================================================================
TELEGRAM_NOTIFICATIONS_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# =============================================================================
# DATABASE (Optional)
# =============================================================================
DATABASE_URL=postgresql://user:password@localhost:5432/lighterbot

# =============================================================================
# MACHINE LEARNING (Optional)
# =============================================================================
ML_ENABLED=false
ML_MIN_TRADES=1000  # Minimum trades before ML training
ML_AUTO_TRAIN=true
ML_RETRAIN_INTERVAL=86400  # Retrain every 24 hours

# =============================================================================
# ADVANCED CONFIGURATION
# =============================================================================
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
LOG_TO_FILE=true
LOG_DIR=logs
LOOP_INTERVAL=1.0  # Main loop interval in seconds
CLOSE_POSITIONS_ON_SHUTDOWN=true
```

### Configuration Validation

Validate your configuration:

```bash
python -c "from config.credentials import get_credentials; creds = get_credentials(); print('✅ Configuration valid')"
```

---

## Security Hardening

### 1. Private Key Management

**NEVER** commit private keys to version control:

```bash
# Verify .gitignore includes:
echo ".env" >> .gitignore
echo "*.key" >> .gitignore
echo "secrets/" >> .gitignore
```

### 2. File Permissions

Restrict access to sensitive files:

```bash
chmod 600 .env
chmod 600 config/credentials.py
```

### 3. Environment Isolation

Use separate environments for testing and production:

```bash
# Testnet environment
LIGHTER_API_URL=https://testnet.zklighter.elliot.ai

# Mainnet environment
LIGHTER_API_URL=https://mainnet.zklighter.elliot.ai
```

### 4. Log Security

Ensure logs don't expose sensitive data:

```bash
# Logs automatically suppress:
# - Private keys
# - API tokens
# - Telegram bot tokens
```

---

## Deployment Options

### Option 1: Direct Execution (Development/Testing)

```bash
# Activate virtual environment
source venv/bin/activate

# Run bot
python -m app.bot
```

### Option 2: Background Process (Production)

```bash
# Start bot in background
nohup python -m app.bot > bot_output.log 2>&1 &

# Save PID for management
echo $! > bot.pid

# Check status
ps aux | grep bot.py

# Stop bot
kill $(cat bot.pid)
```

### Option 3: Systemd Service (Recommended for Production)

Create `/etc/systemd/system/lighterbot.service`:

```ini
[Unit]
Description=LighterBot Trading System
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory=/opt/lighterbot
Environment="PATH=/opt/lighterbot/venv/bin"
ExecStart=/opt/lighterbot/venv/bin/python -m app.bot
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/lighterbot/bot.log
StandardError=append:/var/log/lighterbot/error.log

[Install]
WantedBy=multi-user.target
```

Manage service:

```bash
# Enable service
sudo systemctl enable lighterbot

# Start service
sudo systemctl start lighterbot

# Check status
sudo systemctl status lighterbot

# View logs
sudo journalctl -u lighterbot -f

# Restart service
sudo systemctl restart lighterbot

# Stop service
sudo systemctl stop lighterbot
```

### Option 4: Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "-m", "app.bot"]
```

Build and run:

```bash
# Build image
docker build -t lighterbot:latest .

# Run container
docker run -d \
  --name lighterbot \
  --env-file .env \
  --restart unless-stopped \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  lighterbot:latest

# View logs
docker logs -f lighterbot

# Stop container
docker stop lighterbot
```

### Option 5: Kubernetes Deployment

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lighterbot
spec:
  replicas: 1
  selector:
    matchLabels:
      app: lighterbot
  template:
    metadata:
      labels:
        app: lighterbot
    spec:
      containers:
      - name: lighterbot
        image: lighterbot:latest
        envFrom:
        - secretRef:
            name: lighterbot-secrets
        volumeMounts:
        - name: logs
          mountPath: /app/logs
        - name: data
          mountPath: /app/data
      volumes:
      - name: logs
        persistentVolumeClaim:
          claimName: lighterbot-logs
      - name: data
        persistentVolumeClaim:
          claimName: lighterbot-data
```

---

## Monitoring & Maintenance

### Health Checks

Monitor bot health:

```bash
# Check if bot is running
ps aux | grep bot.py

# Check recent logs
tail -f logs/bot.log

# Check for errors
grep ERROR logs/bot.log | tail -20

# Monitor resource usage
top -p $(cat bot.pid)
```

### Performance Metrics

Key metrics to monitor:

1. **Uptime**: Bot should run 24/7
2. **API Latency**: <500ms per request
3. **WebSocket Status**: Connected (no reconnects)
4. **Position Count**: Within limits
5. **Account Value**: Tracking properly
6. **Kill Switch**: Not triggered

### Telegram Monitoring

Set up Telegram commands:

```
/status     - Show bot status
/position   - View current positions
/balance    - Check account balance
/stats      - Trading statistics
/stop       - Stop trading
/resume     - Resume trading
```

### Log Rotation

Prevent logs from filling disk:

```bash
# Install logrotate configuration
sudo tee /etc/logrotate.d/lighterbot << EOF
/opt/lighterbot/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    copytruncate
}
EOF
```

### Database Maintenance

Regular maintenance tasks:

```sql
-- Vacuum database (weekly)
VACUUM ANALYZE;

-- Archive old trades (monthly)
INSERT INTO trades_archive SELECT * FROM trades WHERE created_at < NOW() - INTERVAL '90 days';
DELETE FROM trades WHERE created_at < NOW() - INTERVAL '90 days';

-- Check database size
SELECT pg_size_pretty(pg_database_size('lighterbot'));
```

---

## Troubleshooting

### Common Issues

#### 1. Bot Won't Start

**Symptoms**: Bot exits immediately

**Solutions**:
```bash
# Check Python version
python --version  # Should be 3.9+

# Verify dependencies
pip install -r requirements.txt

# Check configuration
python -c "from config.credentials import get_credentials; get_credentials()"

# View detailed errors
python -m app.bot 2>&1 | tee startup.log
```

#### 2. API Connection Failures

**Symptoms**: "Connection refused" or timeout errors

**Solutions**:
```bash
# Test network connectivity
curl -I https://mainnet.zklighter.elliot.ai

# Check firewall rules
sudo ufw status

# Verify API credentials
python -c "from app.lighter.lighter_client import LighterClient; import asyncio; asyncio.run(LighterClient(...).connect())"
```

#### 3. WebSocket Disconnects

**Symptoms**: Frequent reconnections

**Solutions**:
- Check network stability
- Increase timeout values
- Use wired connection instead of WiFi
- Contact hosting provider about WebSocket support

#### 4. Kill Switch Triggered

**Symptoms**: Bot stops trading, "Kill switch activated"

**Solutions**:
```bash
# Check account value
python -c "from app.bot import LighterBot; import asyncio; bot = LighterBot(); asyncio.run(bot.initialize()); print(bot.account_state)"

# Reset kill switch (CAUTION)
python reset_killswitch.py

# Review risk settings
grep MAX_DRAWDOWN .env
```

#### 5. Database Connection Issues

**Symptoms**: "Database connection failed"

**Solutions**:
```bash
# Test PostgreSQL connection
psql $DATABASE_URL

# Check PostgreSQL status
sudo systemctl status postgresql

# Verify credentials
echo $DATABASE_URL
```

### Getting Help

1. **Check logs**: `logs/bot.log` for detailed error messages
2. **Enable debug mode**: Set `LOG_LEVEL=DEBUG` in `.env`
3. **Review documentation**: See `ARCHITECTURE.md` and `API.md`
4. **Test components**: Run individual modules to isolate issues
5. **GitHub Issues**: Report bugs with full error logs

---

## Upgrade Procedure

### Upgrading LighterBot

```bash
# 1. Stop bot
sudo systemctl stop lighterbot  # or kill $(cat bot.pid)

# 2. Backup configuration
cp .env .env.backup
cp -r data data.backup

# 3. Pull latest changes
git pull origin main

# 4. Update dependencies
pip install --upgrade -r requirements.txt

# 5. Run migrations (if any)
python -m app.database.migrate

# 6. Restart bot
sudo systemctl start lighterbot
```

### Rollback Procedure

```bash
# 1. Stop bot
sudo systemctl stop lighterbot

# 2. Checkout previous version
git log --oneline  # Find commit hash
git checkout <commit-hash>

# 3. Restore configuration
cp .env.backup .env

# 4. Reinstall dependencies
pip install -r requirements.txt

# 5. Restart bot
sudo systemctl start lighterbot
```

---

## Production Checklist

Before going live with real funds:

- [ ] All tests passed on testnet
- [ ] Configuration reviewed by second person
- [ ] Risk limits appropriate for account size
- [ ] Kill switch tested and verified
- [ ] Monitoring alerts configured
- [ ] Backup system in place
- [ ] Rollback procedure tested
- [ ] Contact information for support
- [ ] Documentation reviewed
- [ ] Regulatory compliance verified (if applicable)

---

## Support

- **Documentation**: See `README.md`, `ARCHITECTURE.md`, `API.md`
- **GitHub Issues**: https://github.com/yourusername/lighterbot/issues
- **Telegram**: Contact @yourusername
- **Email**: support@yourcompany.com

---

**WARNING**: Trading carries significant risk. Never trade with funds you cannot afford to lose. This software is provided "as is" without warranty. Always start with small amounts and testnet before using real funds.
