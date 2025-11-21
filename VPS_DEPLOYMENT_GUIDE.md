# 🚀 VPS Deployment Guide for LighterBot

Complete guide to deploy LighterBot on any VPS (Ubuntu 20.04+)

---

## Quick Start (Automated)

### 1. Download deployment script
```bash
wget https://raw.githubusercontent.com/web3firm/lighterbot/main/deploy_vps.sh
chmod +x deploy_vps.sh
```

### 2. Run installation
```bash
sudo ./deploy_vps.sh
```

The script will:
- ✅ Install all dependencies (Python 3.9, Git, PostgreSQL, etc.)
- ✅ Create dedicated `lighterbot` user
- ✅ Clone repository to `/opt/lighterbot`
- ✅ Setup Python virtual environment
- ✅ Configure environment variables (interactive prompts)
- ✅ Create systemd service for auto-start
- ✅ Setup log rotation
- ✅ Configure firewall (UFW)
- ✅ Install health monitoring (runs every 5 minutes)

### 3. Start the bot
```bash
sudo systemctl start lighterbot
sudo systemctl status lighterbot
```

---

## Manual Deployment (Step-by-Step)

### Prerequisites

**VPS Requirements:**
- Ubuntu 20.04+ (or Debian 11+)
- 2GB RAM minimum (4GB recommended)
- 10GB disk space
- Root/sudo access

**Recommended VPS Providers:**
- DigitalOcean ($10/month droplet)
- Vultr ($6/month)
- Linode ($5/month)
- AWS EC2 (t3.small)
- Google Cloud (e2-small)

### Step 1: Connect to VPS

```bash
ssh root@your-vps-ip
```

### Step 2: Update System

```bash
apt update && apt upgrade -y
```

### Step 3: Install Dependencies

```bash
# Install Python 3.9+
apt install -y python3.9 python3.9-venv python3.9-dev python3-pip

# Install Git
apt install -y git curl build-essential

# Install system tools
apt install -y supervisor ufw fail2ban htop
```

### Step 4: Create Application User

```bash
# Create dedicated user (security best practice)
useradd -r -m -d /home/lighterbot -s /bin/bash lighterbot

# Switch to lighterbot user
sudo -u lighterbot -i
```

### Step 5: Clone Repository

```bash
cd /opt
sudo mkdir lighterbot
sudo chown lighterbot:lighterbot lighterbot
cd lighterbot

# Clone repo
git clone https://github.com/web3firm/lighterbot.git .
```

### Step 6: Setup Python Environment

```bash
# Create virtual environment
python3.9 -m venv venv

# Activate environment
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 7: Configure Environment

```bash
# Copy .env.example
cp .env.example .env

# Edit configuration
nano .env
```

**Required Configuration:**
```env
# Lighter Protocol
LIGHTER_API_URL=https://mainnet.zklighter.elliot.ai
LIGHTER_API_PRIVATE_KEY=your_private_key_here
LIGHTER_API_KEY_INDEX=0
LIGHTER_ACCOUNT_INDEX=0
LIGHTER_MARKET_ID=0

# Trading Settings
TRADING_SYMBOL=ETH-USD
MAX_LEVERAGE=5
POSITION_SIZE_PCT=50
TP_PNL_PCT=15
SL_PNL_PCT=5
MAX_DAILY_LOSS_PCT=10
MAX_OPEN_POSITIONS=1
POSITION_COOLDOWN_SECONDS=30

# Telegram (Optional)
TELEGRAM_NOTIFICATIONS_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

**Secure .env file:**
```bash
chmod 600 .env
chown lighterbot:lighterbot .env
```

### Step 8: Test Bot

```bash
# Test run (should show initialization logs)
python -m app.bot

# If successful, press Ctrl+C to stop
```

### Step 9: Setup Systemd Service

```bash
# Create service file
sudo nano /etc/systemd/system/lighterbot.service
```

**Service Configuration:**
```ini
[Unit]
Description=LighterBot Trading Bot
After=network.target

[Service]
Type=simple
User=lighterbot
Group=lighterbot
WorkingDirectory=/opt/lighterbot
Environment="PATH=/opt/lighterbot/venv/bin"
ExecStart=/opt/lighterbot/venv/bin/python -m app.bot
Restart=always
RestartSec=10
StandardOutput=append:/var/log/lighterbot/bot.log
StandardError=append:/var/log/lighterbot/error.log

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/lighterbot/logs /opt/lighterbot/data /var/log/lighterbot

[Install]
WantedBy=multi-user.target
```

**Create log directory:**
```bash
sudo mkdir -p /var/log/lighterbot
sudo chown lighterbot:lighterbot /var/log/lighterbot
```

**Enable and start service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable lighterbot
sudo systemctl start lighterbot
sudo systemctl status lighterbot
```

### Step 10: Setup Log Rotation

```bash
sudo nano /etc/logrotate.d/lighterbot
```

```
/var/log/lighterbot/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    copytruncate
    create 0640 lighterbot lighterbot
}

/opt/lighterbot/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    copytruncate
}
```

### Step 11: Configure Firewall

```bash
# Enable firewall
sudo ufw enable

# Allow SSH
sudo ufw allow OpenSSH

# Allow HTTPS (for API)
sudo ufw allow 443/tcp

# Check status
sudo ufw status
```

### Step 12: Setup Monitoring (Optional)

Create health check script:

```bash
nano /opt/lighterbot/monitor.sh
```

```bash
#!/bin/bash
# Health check script

SERVICE="lighterbot"
LOG="/var/log/lighterbot/monitor.log"

if ! systemctl is-active --quiet $SERVICE; then
    echo "$(date): Service down, restarting..." >> $LOG
    systemctl restart $SERVICE
fi

# Check disk space
USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $USAGE -gt 90 ]; then
    echo "$(date): WARNING - Disk usage at ${USAGE}%" >> $LOG
fi
```

```bash
chmod +x /opt/lighterbot/monitor.sh

# Add to crontab (runs every 5 minutes)
sudo crontab -e
```

Add line:
```
*/5 * * * * /opt/lighterbot/monitor.sh
```

---

## Managing the Bot

### Start/Stop/Restart

```bash
# Start
sudo systemctl start lighterbot

# Stop
sudo systemctl stop lighterbot

# Restart
sudo systemctl restart lighterbot

# Status
sudo systemctl status lighterbot
```

### View Logs

```bash
# Real-time logs
sudo journalctl -u lighterbot -f

# Application logs
tail -f /var/log/lighterbot/bot.log

# Error logs
tail -f /var/log/lighterbot/error.log

# Last 100 lines
sudo journalctl -u lighterbot -n 100
```

### Update Bot

```bash
# Stop service
sudo systemctl stop lighterbot

# Update code
cd /opt/lighterbot
sudo -u lighterbot git pull

# Install new dependencies (if any)
sudo -u lighterbot bash -c "source venv/bin/activate && pip install -r requirements.txt"

# Restart service
sudo systemctl start lighterbot
```

### Configuration Changes

```bash
# Edit .env
sudo nano /opt/lighterbot/.env

# Restart to apply changes
sudo systemctl restart lighterbot
```

---

## Monitoring & Maintenance

### Check Bot Health

```bash
# Service status
sudo systemctl status lighterbot

# CPU/Memory usage
htop
top -u lighterbot

# Disk space
df -h

# Network connections
sudo netstat -tulpn | grep python
```

### View Statistics

```bash
# Today's trades
cat /opt/lighterbot/data/trades/trades_$(date +%Y%m%d).jsonl

# Trading stats (via Telegram)
# Send /stats to your Telegram bot
```

### Backup Data

```bash
# Create backup directory
mkdir -p ~/backups

# Backup configuration and data
tar -czf ~/backups/lighterbot-$(date +%Y%m%d).tar.gz \
    /opt/lighterbot/.env \
    /opt/lighterbot/data

# Copy to local machine
scp root@your-vps-ip:~/backups/lighterbot-*.tar.gz .
```

### Database Backup (if using PostgreSQL)

```bash
# Backup database
pg_dump lighterbot > ~/backups/lighterbot-db-$(date +%Y%m%d).sql

# Restore database
psql lighterbot < ~/backups/lighterbot-db-20250121.sql
```

---

## Troubleshooting

### Bot Won't Start

**Check logs:**
```bash
sudo journalctl -u lighterbot -n 50
tail -n 50 /var/log/lighterbot/error.log
```

**Common issues:**
1. **Invalid credentials** - Check `.env` file
2. **Python dependencies** - Reinstall: `pip install -r requirements.txt`
3. **Port conflicts** - Check if another process is using ports
4. **Permission errors** - Verify file ownership: `chown -R lighterbot:lighterbot /opt/lighterbot`

### API Connection Errors

```bash
# Test API connectivity
curl -I https://mainnet.zklighter.elliot.ai

# Check DNS resolution
nslookup mainnet.zklighter.elliot.ai

# Test with bot
cd /opt/lighterbot
source venv/bin/activate
python -c "from app.lighter.lighter_client import LighterClient; print('OK')"
```

### High Memory Usage

```bash
# Check memory
free -h

# Restart bot to free memory
sudo systemctl restart lighterbot

# Add swap (if needed)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Bot Keeps Restarting

**Check crash logs:**
```bash
sudo journalctl -u lighterbot -p err -n 50
```

**Common causes:**
1. Kill switch triggered (check daily loss limit)
2. API errors (check credentials)
3. Network issues (check connectivity)
4. Out of memory (add swap or upgrade VPS)

---

## Security Best Practices

### 1. SSH Security

```bash
# Disable root login
sudo nano /etc/ssh/sshd_config
# Set: PermitRootLogin no

# Use SSH keys instead of passwords
ssh-copy-id user@vps-ip

# Restart SSH
sudo systemctl restart sshd
```

### 2. Firewall Rules

```bash
# Only allow necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. Fail2Ban (Brute Force Protection)

```bash
# Install
sudo apt install fail2ban

# Enable
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 4. Secure Private Keys

```bash
# Never commit .env to git
echo ".env" >> .gitignore

# Restrict .env permissions
chmod 600 /opt/lighterbot/.env

# Use environment variables or secrets manager for production
```

### 5. Regular Updates

```bash
# Update system weekly
sudo apt update && sudo apt upgrade -y

# Update bot code regularly
cd /opt/lighterbot && git pull
```

---

## Performance Optimization

### 1. Use SSD Storage
- Faster I/O for logs and database
- Recommended for production

### 2. Optimize Python
```bash
# Use production WSGI server (if adding web interface)
pip install gunicorn

# Enable Python optimizations
export PYTHONOPTIMIZE=1
```

### 3. Database Optimization (if using PostgreSQL)
```sql
-- Create indexes
CREATE INDEX idx_trades_created_at ON trades(created_at);
CREATE INDEX idx_trades_symbol ON trades(symbol);

-- Vacuum regularly
VACUUM ANALYZE;
```

### 4. Log Management
```bash
# Compress old logs
find /var/log/lighterbot -name "*.log" -mtime +7 -exec gzip {} \;

# Delete very old logs
find /var/log/lighterbot -name "*.gz" -mtime +30 -delete
```

---

## Cost Optimization

### VPS Provider Comparison

| Provider | CPU | RAM | Storage | Price | Notes |
|----------|-----|-----|---------|-------|-------|
| DigitalOcean | 1 core | 2GB | 50GB | $12/mo | Recommended |
| Vultr | 1 core | 2GB | 55GB | $10/mo | Good value |
| Linode | 1 core | 2GB | 50GB | $12/mo | Reliable |
| AWS EC2 | t3.small | 2GB | 20GB | ~$15/mo | Enterprise |
| Hetzner | 1 core | 2GB | 40GB | €4.5/mo | Budget |

### Reduce Costs

1. **Use Reserved Instances** (AWS, GCP) - Save 30-50%
2. **Enable Auto-Shutdown** for testing bots
3. **Use Spot Instances** for non-critical environments
4. **Optimize resources** - 2GB RAM sufficient for most cases

---

## Advanced Setup

### Docker Deployment

```bash
# Create Dockerfile
cat > Dockerfile << 'EOF'
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "-m", "app.bot"]
EOF

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
```

### Multiple Bots (Different Symbols)

```bash
# Copy bot directory
cp -r /opt/lighterbot /opt/lighterbot-btc

# Edit .env for BTC
cd /opt/lighterbot-btc
nano .env  # Change TRADING_SYMBOL=BTC-USD

# Create new service
sudo cp /etc/systemd/system/lighterbot.service \
        /etc/systemd/system/lighterbot-btc.service

# Edit service file
sudo nano /etc/systemd/system/lighterbot-btc.service
# Change WorkingDirectory to /opt/lighterbot-btc

# Start second bot
sudo systemctl enable lighterbot-btc
sudo systemctl start lighterbot-btc
```

---

## Support & Resources

### Documentation
- [Full Deployment Guide](md_files/DEPLOYMENT.md)
- [Architecture](md_files/ARCHITECTURE.md)
- [Changelog](md_files/CHANGELOG.md)

### Community
- GitHub Issues: https://github.com/web3firm/lighterbot/issues
- Lighter Protocol Discord: https://discord.gg/lighter

### Emergency Contact
- Kill switch: Set `MAX_DAILY_LOSS_PCT=0.1` to halt trading
- Manual stop: `sudo systemctl stop lighterbot`
- Close positions: Login to Lighter Protocol UI

---

## Quick Reference

```bash
# Start bot
sudo systemctl start lighterbot

# Stop bot
sudo systemctl stop lighterbot

# Restart bot
sudo systemctl restart lighterbot

# View logs
sudo journalctl -u lighterbot -f

# Check status
sudo systemctl status lighterbot

# Update bot
cd /opt/lighterbot && git pull && sudo systemctl restart lighterbot

# Edit config
sudo nano /opt/lighterbot/.env

# Monitor resources
htop

# Backup data
tar -czf backup.tar.gz /opt/lighterbot/.env /opt/lighterbot/data
```

---

**Happy Trading! 🚀**

*For questions or issues, open an issue on GitHub or contact support.*
