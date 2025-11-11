"""
Telegram Bot Controller for Lighter Trading Bot
Comprehensive remote control and monitoring via Telegram
"""
import asyncio
import os
import signal
import subprocess
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any
import psutil
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from logger import logger

# Import trading modules for data access
try:
    from market_data import MarketData
    from lighter_client import get_client
    from utils import market_metadata, format_price, format_size, format_pnl
    TRADING_MODULES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Trading modules not available: {e}")
    TRADING_MODULES_AVAILABLE = False


def get_current_settings():
    """Get fresh settings by reloading config"""
    # Reload env variables with explicit path
    import os
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        env_path = '.env'  # Fallback to current directory
    load_dotenv(dotenv_path=env_path, override=True)
    # Reimport settings to get fresh values
    from config import Settings
    return Settings()
try:
    from market_data import MarketData
    from lighter_client import get_client
    from utils import market_metadata, format_price, format_size, format_pnl
    TRADING_MODULES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Trading modules not available: {e}")
    TRADING_MODULES_AVAILABLE = False


class TradingDataFetcher:
    """Fetches live trading data"""
    
    def __init__(self):
        self.md = MarketData() if TRADING_MODULES_AVAILABLE else None
    
    async def get_current_price(self) -> Dict[str, Any]:
        """Get current market price"""
        try:
            if not TRADING_MODULES_AVAILABLE:
                return {"error": "Trading modules not available"}
            
            price = await self.md.get_current_price()
            bid, ask = await self.md.get_best_bid_ask()
            spread = ask - bid
            spread_bps = (spread / bid * 10000) if bid > 0 else 0
            
            return {
                "price": price,
                "bid": bid,
                "ask": ask,
                "spread": spread,
                "spread_bps": spread_bps
            }
        except Exception as e:
            logger.error(f"Error getting price: {e}")
            return {"error": str(e)}
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        try:
            if not TRADING_MODULES_AVAILABLE:
                return {"error": "Trading modules not available"}
            
            client = await get_client()
            account = await client.get_account_info()
            
            return account
        except Exception as e:
            logger.error(f"Error getting account: {e}")
            return {"error": str(e)}
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get open positions"""
        try:
            if not TRADING_MODULES_AVAILABLE:
                return []
            
            client = await get_client()
            account = await client.get_account_info()
            
            # Extract positions from account data
            positions = []
            if isinstance(account, dict):
                # Account data is nested in 'accounts' array
                if 'accounts' in account and len(account['accounts']) > 0:
                    acc_data = account['accounts'][0]
                    positions = acc_data.get('positions', [])
                    # Filter only positions with non-zero size
                    positions = [p for p in positions if float(p.get('position', 0)) != 0]
                # Fallback for different structure
                elif 'positions' in account:
                    positions = account['positions']
                elif 'data' in account and 'positions' in account['data']:
                    positions = account['data']['positions']
            
            return positions if positions else []
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    async def get_recent_trades(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent trades"""
        try:
            if not TRADING_MODULES_AVAILABLE:
                return []
            
            trades = await self.md.get_recent_trades(limit=limit)
            return trades[:limit] if trades else []
        except Exception as e:
            logger.error(f"Error getting trades: {e}")
            return []
    
    async def get_active_orders(self) -> List[Dict[str, Any]]:
        """Get active orders"""
        try:
            if not TRADING_MODULES_AVAILABLE:
                return []
            
            settings = get_current_settings()
            client = await get_client()
            orders = await client.get_active_orders(settings.trading_market_id)
            
            if isinstance(orders, dict) and 'orders' in orders:
                return orders['orders']
            elif isinstance(orders, list):
                return orders
            
            return []
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []
    
    async def get_balance(self) -> Dict[str, Any]:
        """Get account balance"""
        try:
            if not TRADING_MODULES_AVAILABLE:
                return {"error": "Trading modules not available"}
            
            client = await get_client()
            account = await client.get_account_info()
            
            balance_info = {
                "total": 0,
                "available": 0,
                "locked": 0,
                "currency": "USDC"
            }
            
            if isinstance(account, dict):
                # Account data is nested in 'accounts' array
                if 'accounts' in account and len(account['accounts']) > 0:
                    acc_data = account['accounts'][0]
                    balance_info['available'] = float(acc_data.get('available_balance', 0))
                    balance_info['total'] = float(acc_data.get('total_asset_value', 0))
                    # Calculate locked (collateral - available)
                    collateral = float(acc_data.get('collateral', 0))
                    balance_info['locked'] = collateral - balance_info['available']
                # Fallback for different structure
                elif 'available_balance' in account:
                    balance_info['available'] = float(account.get('available_balance', 0))
                    balance_info['total'] = float(account.get('total_asset_value', balance_info['available']))
            
            return balance_info
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return {"error": str(e)}
    
    async def get_portfolio_stats(self) -> Dict[str, Any]:
        """Get portfolio statistics"""
        try:
            if not TRADING_MODULES_AVAILABLE:
                return {"error": "Trading modules not available"}
            
            balance = await self.get_balance()
            positions = await self.get_positions()
            orders = await self.get_active_orders()
            price_data = await self.get_current_price()
            
            # Calculate stats
            total_value = balance.get('total', 0)
            position_count = len(positions)
            open_orders_count = len(orders)
            
            # Calculate position value and PnL
            position_value = 0
            unrealized_pnl = 0
            
            for pos in positions:
                if isinstance(pos, dict):
                    # Position size from API
                    size = float(pos.get('position', 0))
                    entry_price = float(pos.get('avg_entry_price', 0))
                    current_price = price_data.get('price', 0)
                    
                    # Calculate value and PnL
                    pos_value = abs(size) * current_price
                    pnl = size * (current_price - entry_price)
                    
                    position_value += pos_value
                    unrealized_pnl += pnl
            
            return {
                "total_value": total_value,
                "available": balance.get('available', 0),
                "locked": balance.get('locked', 0),
                "position_count": position_count,
                "position_value": position_value,
                "open_orders": open_orders_count,
                "unrealized_pnl": unrealized_pnl,
                "current_price": price_data.get('price', 0)
            }
        except Exception as e:
            logger.error(f"Error getting portfolio stats: {e}")
            return {"error": str(e)}


# Global data fetcher
data_fetcher = TradingDataFetcher()


class TradingBotController:
    """Controller for the trading bot process"""
    
    def __init__(self):
        self.bot_process: Optional[subprocess.Popen] = None
        self.bot_pid: Optional[int] = None
        
    def is_running(self) -> bool:
        """Check if the bot is currently running"""
        try:
            # Check if we have a stored PID
            if os.path.exists('data/bot.pid'):
                with open('data/bot.pid', 'r') as f:
                    pid = int(f.read().strip())
                    if psutil.pid_exists(pid):
                        proc = psutil.Process(pid)
                        if 'python' in proc.name().lower() and 'main.py' in ' '.join(proc.cmdline()):
                            self.bot_pid = pid
                            return True
            
            # Search for running process
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and 'python' in proc.info['name'].lower():
                        if any('main.py' in arg for arg in cmdline):
                            self.bot_pid = proc.info['pid']
                            # Save PID
                            os.makedirs('data', exist_ok=True)
                            with open('data/bot.pid', 'w') as f:
                                f.write(str(self.bot_pid))
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return False
        except Exception as e:
            logger.error(f"Error checking bot status: {e}")
            return False
    
    def start_bot(self) -> tuple[bool, str]:
        """Start the trading bot"""
        try:
            if self.is_running():
                return False, "❌ Bot is already running!"
            
            # Start bot in background
            import time
            self.bot_process = subprocess.Popen(
                [sys.executable, 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                start_new_session=True
            )
            
            self.bot_pid = self.bot_process.pid
            
            # Save PID
            os.makedirs('data', exist_ok=True)
            with open('data/bot.pid', 'w') as f:
                f.write(str(self.bot_pid))
            
            # Wait a moment to check if it started successfully
            time.sleep(2)
            
            if self.is_running():
                return True, f"✅ Bot started successfully! PID: {self.bot_pid}"
            else:
                return False, "❌ Bot failed to start. Check logs for details."
                
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            return False, f"❌ Error: {str(e)}"
    
    def stop_bot(self) -> tuple[bool, str]:
        """Stop the trading bot"""
        try:
            if not self.is_running():
                return False, "❌ Bot is not running!"
            
            # Send SIGTERM for graceful shutdown
            import time
            os.kill(self.bot_pid, signal.SIGTERM)
            
            # Wait for process to terminate
            for _ in range(10):
                if not self.is_running():
                    # Clean up PID file
                    if os.path.exists('data/bot.pid'):
                        os.remove('data/bot.pid')
                    return True, "✅ Bot stopped successfully!"
                time.sleep(1)
            
            # Force kill if still running
            os.kill(self.bot_pid, signal.SIGKILL)
            if os.path.exists('data/bot.pid'):
                os.remove('data/bot.pid')
            
            return True, "✅ Bot force stopped!"
            
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
            return False, f"❌ Error: {str(e)}"
    
    def restart_bot(self) -> tuple[bool, str]:
        """Restart the trading bot"""
        import time
        # Stop first
        success, msg = self.stop_bot()
        if not success and "not running" not in msg.lower():
            return False, msg
        
        # Wait a moment
        time.sleep(2)
        
        # Start again
        return self.start_bot()
    
    def get_status(self) -> str:
        """Get bot status information"""
        try:
            if not self.is_running():
                return "📊 *Bot Status*\n\n❌ Bot is NOT running\n\nUse /start_bot to start it."
            
            # Get process info
            proc = psutil.Process(self.bot_pid)
            
            # Calculate uptime
            create_time = datetime.fromtimestamp(proc.create_time())
            uptime = datetime.now() - create_time
            hours = uptime.total_seconds() / 3600
            
            # Get memory usage
            memory_mb = proc.memory_info().rss / 1024 / 1024
            
            # Get CPU usage
            cpu_percent = proc.cpu_percent(interval=1)
            
            # Read recent logs
            log_lines = []
            try:
                with open('bot.log', 'r') as f:
                    lines = f.readlines()
                    log_lines = lines[-5:] if len(lines) >= 5 else lines
            except:
                log_lines = ["No logs available"]
            
            status = f"""📊 *Bot Status*

✅ Status: RUNNING
🆔 PID: {self.bot_pid}
⏱️ Uptime: {hours:.1f} hours
💾 Memory: {memory_mb:.1f} MB
⚙️ CPU: {cpu_percent:.1f}%

📈 Network: {settings.lighter_base_url.split('//')[1].split('.')[0].upper()}
🎯 Market: {settings.trading_symbol}
🔒 DRY_RUN: {settings.dry_run}

📝 Recent Logs:
```
{"".join(log_lines[-3:]).strip()}
```
"""
            return status
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return f"❌ Error getting status: {str(e)}"
    
    def get_logs(self, lines: int = 20) -> str:
        """Get recent log lines"""
        try:
            with open('bot.log', 'r') as f:
                all_lines = f.readlines()
                recent = all_lines[-lines:] if len(all_lines) >= lines else all_lines
                return "".join(recent)
        except Exception as e:
            return f"Error reading logs: {str(e)}"


# Global controller instance
controller = TradingBotController()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    # Get fresh settings
    settings = get_current_settings()
    
    keyboard = [
        [
            InlineKeyboardButton("▶️ Start Bot", callback_data="start_bot"),
            InlineKeyboardButton("⏹️ Stop Bot", callback_data="stop_bot")
        ],
        [
            InlineKeyboardButton("🔄 Restart Bot", callback_data="restart_bot"),
            InlineKeyboardButton("📊 Status", callback_data="status")
        ],
        [
            InlineKeyboardButton("� Portfolio", callback_data="portfolio"),
            InlineKeyboardButton("📈 Positions", callback_data="positions")
        ],
        [
            InlineKeyboardButton("💵 Balance", callback_data="balance"),
            InlineKeyboardButton("📋 Orders", callback_data="orders")
        ],
        [
            InlineKeyboardButton("🔄 Trades", callback_data="trades"),
            InlineKeyboardButton("💹 Price", callback_data="price")
        ],
        [
            InlineKeyboardButton("�📝 Logs", callback_data="logs"),
            InlineKeyboardButton("⚙️ Config", callback_data="config")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_msg = f"""🤖 *Lighter Trading Bot Controller*

Welcome! Full remote control and monitoring.

*Bot Status:* {"✅ RUNNING" if controller.is_running() else "❌ STOPPED"}
*Network:* {settings.lighter_base_url.split('//')[1].split('.')[0].upper()}
*Market:* {settings.trading_symbol} (ID: {settings.trading_market_id})
*DRY RUN:* {settings.dry_run}

📱 *Quick Commands:*
/price - Current price
/portfolio - Portfolio overview
/positions - Open positions
/balance - Account balance
/orders - Active orders
/trades - Recent trades
/status - Bot status
"""
    
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')


async def start_bot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start_bot command"""
    success, msg = controller.start_bot()
    
    keyboard = [[InlineKeyboardButton("📊 Check Status", callback_data="status")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg, reply_markup=reply_markup)


async def stop_bot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop_bot command"""
    success, msg = controller.stop_bot()
    
    keyboard = [[InlineKeyboardButton("▶️ Start Again", callback_data="start_bot")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg, reply_markup=reply_markup)


async def restart_bot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /restart_bot command"""
    await update.message.reply_text("🔄 Restarting bot...")
    success, msg = controller.restart_bot()
    
    keyboard = [[InlineKeyboardButton("📊 Check Status", callback_data="status")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg, reply_markup=reply_markup)


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    status = controller.get_status()
    
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="status"),
            InlineKeyboardButton("📝 Logs", callback_data="logs")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(status, reply_markup=reply_markup, parse_mode='Markdown')


async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /logs command"""
    logs = controller.get_logs(30)
    
    # Telegram message limit is 4096 chars
    if len(logs) > 4000:
        logs = logs[-4000:]
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="logs")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(f"📝 *Recent Logs:*\n```\n{logs}\n```", 
                                   reply_markup=reply_markup, 
                                   parse_mode='Markdown')


async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /config command"""
    # Get fresh settings
    settings = get_current_settings()
    
    config_info = f"""⚙️ *Configuration*

🌐 Network: {settings.lighter_base_url}
🎯 Market: {settings.trading_symbol} (ID: {settings.trading_market_id})

💰 Trading:
  • Max Position: {settings.max_position_size}
  • Max Leverage: {settings.max_leverage}x
  • Min Order: {settings.min_order_size}

🛡️ Risk:
  • Max Drawdown: {settings.max_daily_drawdown * 100}%
  • Liquidation Threshold: {settings.liquidation_threshold * 100}%
  • Max Open Orders: {settings.max_open_orders}

📊 Strategies:
  • Momentum: {settings.enable_momentum_strategy}
  • Mean Reversion: {settings.enable_mean_reversion_strategy}
  • Order Flow: {settings.enable_orderflow_strategy}
  • Sentiment: {settings.enable_sentiment_strategy}

🔒 Safety:
  • DRY_RUN: {settings.dry_run}
  • Testnet: {settings.use_testnet}

⚙️ To change config, edit .env on server
"""
    
    await update.message.reply_text(config_info, parse_mode='Markdown')


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    # Get fresh settings for all actions
    settings = get_current_settings()
    
    action = query.data
    
    if action == "start_bot":
        success, msg = controller.start_bot()
        keyboard = [[InlineKeyboardButton("📊 Check Status", callback_data="status")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(msg, reply_markup=reply_markup)
        
    elif action == "stop_bot":
        success, msg = controller.stop_bot()
        keyboard = [[InlineKeyboardButton("▶️ Start Again", callback_data="start_bot")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(msg, reply_markup=reply_markup)
        
    elif action == "restart_bot":
        await query.edit_message_text("🔄 Restarting bot...")
        success, msg = controller.restart_bot()
        keyboard = [[InlineKeyboardButton("📊 Check Status", callback_data="status")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(msg, reply_markup=reply_markup)
        
    elif action == "status":
        status = controller.get_status()
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="status"),
                InlineKeyboardButton("📝 Logs", callback_data="logs")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(status, reply_markup=reply_markup, parse_mode='Markdown')
        
    elif action == "logs":
        logs = controller.get_logs(30)
        if len(logs) > 4000:
            logs = logs[-4000:]
        
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="logs")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"📝 *Recent Logs:*\n```\n{logs}\n```", 
                                      reply_markup=reply_markup, 
                                      parse_mode='Markdown')
        
    elif action == "config":
        config_info = f"""⚙️ *Configuration*

🌐 Network: {settings.lighter_base_url}
🎯 Market: {settings.trading_symbol} (ID: {settings.trading_market_id})

💰 Trading:
  • Max Position: {settings.max_position_size}
  • Max Leverage: {settings.max_leverage}x
  • Min Order: {settings.min_order_size}

🛡️ Risk:
  • Max Drawdown: {settings.max_daily_drawdown * 100}%
  • Liquidation Threshold: {settings.liquidation_threshold * 100}%
  • Max Open Orders: {settings.max_open_orders}

📊 Strategies:
  • Momentum: {settings.enable_momentum_strategy}
  • Mean Reversion: {settings.enable_mean_reversion_strategy}
  • Order Flow: {settings.enable_orderflow_strategy}
  • Sentiment: {settings.enable_sentiment_strategy}

🔒 Safety:
  • DRY_RUN: {settings.dry_run}
  • Testnet: {settings.use_testnet}
"""
        await query.edit_message_text(config_info, parse_mode='Markdown')
        
    elif action == "price":
        await query.edit_message_text("💹 Fetching price...")
        price_data = await data_fetcher.get_current_price()
        
        if 'error' in price_data:
            await query.edit_message_text(f"❌ Error: {price_data['error']}")
            return
        
        price_msg = f"""💹 *{settings.trading_symbol} Price*

💰 Current: ${price_data['price']:,.2f}
📊 Bid: ${price_data['bid']:,.2f}
📊 Ask: ${price_data['ask']:,.2f}
📏 Spread: ${price_data['spread']:.2f} ({price_data['spread_bps']:.2f} bps)

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="price")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(price_msg, reply_markup=reply_markup, parse_mode='Markdown')
        
    elif action == "portfolio":
        await query.edit_message_text("💰 Loading portfolio...")
        stats = await data_fetcher.get_portfolio_stats()
        
        if 'error' in stats:
            await query.edit_message_text(f"❌ Error: {stats['error']}")
            return
        
        pnl_emoji = "📈" if stats['unrealized_pnl'] >= 0 else "📉"
        pnl_sign = "+" if stats['unrealized_pnl'] >= 0 else ""
        
        portfolio_msg = f"""💼 *Portfolio Overview*

💵 *Balance:*
  Total: ${stats['total_value']:,.2f}
  Available: ${stats['available']:,.2f}
  Locked: ${stats['locked']:,.2f}

📊 *Positions:*
  Open: {stats['position_count']}
  Value: ${stats['position_value']:,.2f}
  {pnl_emoji} P&L: {pnl_sign}${stats['unrealized_pnl']:,.2f}

📋 *Orders:*
  Active: {stats['open_orders']}

💹 *Current Price:*
  {settings.trading_symbol}: ${stats['current_price']:,.2f}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="portfolio"),
                InlineKeyboardButton("📈 Positions", callback_data="positions")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(portfolio_msg, reply_markup=reply_markup, parse_mode='Markdown')
        
    elif action == "positions":
        await query.edit_message_text("📈 Loading positions...")
        positions = await data_fetcher.get_positions()
        price_data = await data_fetcher.get_current_price()
        current_price = price_data.get('price', 0)
        
        if not positions:
            positions_msg = f"""📈 *Open Positions*

No open positions

💹 Current Price: ${current_price:,.2f}
"""
        else:
            positions_msg = f"""📈 *Open Positions* ({len(positions)})\n\n"""
            
            for i, pos in enumerate(positions[:10], 1):
                if isinstance(pos, dict):
                    # Use correct field names from API
                    size = float(pos.get('position', 0))
                    entry_price = float(pos.get('avg_entry_price', 0))
                    symbol = pos.get('symbol', settings.trading_symbol)
                    side = "🟢 LONG" if size > 0 else "🔴 SHORT"
                    
                    pnl = size * (current_price - entry_price)
                    pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                    pnl_emoji = "📈" if pnl >= 0 else "📉"
                    
                    positions_msg += f"""*Position #{i}* ({symbol})
{side} {abs(size):.4f}
Entry: ${entry_price:,.2f}
Current: ${current_price:,.2f}
{pnl_emoji} P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)

"""
        
        positions_msg += f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="positions")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(positions_msg, reply_markup=reply_markup, parse_mode='Markdown')
        
    elif action == "balance":
        await query.edit_message_text("💵 Loading balance...")
        balance = await data_fetcher.get_balance()
        
        if 'error' in balance:
            await query.edit_message_text(f"❌ Error: {balance['error']}")
            return
        
        balance_msg = f"""💵 *Account Balance*

💰 Total: ${balance['total']:,.2f} {balance['currency']}
✅ Available: ${balance['available']:,.2f}
🔒 Locked: ${balance['locked']:,.2f}

📊 Utilization: {(balance['locked'] / balance['total'] * 100) if balance['total'] > 0 else 0:.1f}%

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="balance")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(balance_msg, reply_markup=reply_markup, parse_mode='Markdown')
        
    elif action == "orders":
        await query.edit_message_text("📋 Loading orders...")
        orders = await data_fetcher.get_active_orders()
        
        if not orders:
            orders_msg = f"""📋 *Active Orders*

No active orders

🕐 {datetime.now().strftime('%H:%M:%S')}
"""
        else:
            orders_msg = f"""📋 *Active Orders* ({len(orders)})\n\n"""
            
            for i, order in enumerate(orders[:10], 1):
                if isinstance(order, dict):
                    side = order.get('side', 'UNKNOWN')
                    order_type = order.get('type', 'LIMIT')
                    size = float(order.get('size', 0))
                    price = float(order.get('price', 0))
                    
                    side_emoji = "🟢" if side == "BUY" else "🔴"
                    
                    orders_msg += f"""*Order #{i}*
{side_emoji} {side} {order_type}
Size: {size}
Price: ${price:,.2f}

"""
        
        orders_msg += f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="orders")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(orders_msg, reply_markup=reply_markup, parse_mode='Markdown')
        
    elif action == "trades":
        await query.edit_message_text("🔄 Loading trades...")
        trades = await data_fetcher.get_recent_trades(limit=5)
        
        if not trades:
            trades_msg = f"""🔄 *Recent Trades*

No recent trades

🕐 {datetime.now().strftime('%H:%M:%S')}
"""
        else:
            trades_msg = f"""🔄 *Recent Market Trades* (Last {len(trades)})\n\n"""
            
            for i, trade in enumerate(trades, 1):
                if isinstance(trade, dict):
                    price = float(trade.get('price', 0))
                    size = float(trade.get('size', 0))
                    side = trade.get('side', 'UNKNOWN')
                    
                    side_emoji = "🟢" if side == "BUY" else "🔴"
                    
                    trades_msg += f"""{side_emoji} {side} {size} @ ${price:,.2f}

"""
        
        trades_msg += f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="trades")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(trades_msg, reply_markup=reply_markup, parse_mode='Markdown')


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """🤖 *Bot Commands*

*Bot Control:*
/start - Main control panel
/start_bot - Start the trading bot
/stop_bot - Stop the trading bot
/restart_bot - Restart the trading bot
/status - Bot status & metrics

*Trading Info:*
/price - Current market price
/portfolio - Portfolio overview
/positions - Open positions
/balance - Account balance
/orders - Active orders
/trades - Recent trades (last 5)

*Configuration:*
/config - View configuration
/logs - View recent logs
/help - This help message

💡 *Tips:*
• Use buttons for easy control
• Check portfolio regularly
• Monitor positions closely
• Review logs for errors
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def price_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /price command - show current price"""
    # Get fresh settings
    settings = get_current_settings()
    
    await update.message.reply_text("💹 Fetching current price...")
    
    price_data = await data_fetcher.get_current_price()
    
    if 'error' in price_data:
        await update.message.reply_text(f"❌ Error: {price_data['error']}")
        return
    
    price_msg = f"""💹 *{settings.trading_symbol} Price*

💰 Current: ${price_data['price']:,.2f}
📊 Bid: ${price_data['bid']:,.2f}
📊 Ask: ${price_data['ask']:,.2f}
📏 Spread: ${price_data['spread']:.2f} ({price_data['spread_bps']:.2f} bps)

🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="price")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(price_msg, reply_markup=reply_markup, parse_mode='Markdown')


async def portfolio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /portfolio command - show portfolio overview"""
    # Get fresh settings
    settings = get_current_settings()
    
    await update.message.reply_text("💰 Loading portfolio...")
    
    stats = await data_fetcher.get_portfolio_stats()
    
    if 'error' in stats:
        await update.message.reply_text(f"❌ Error: {stats['error']}")
        return
    
    pnl_emoji = "📈" if stats['unrealized_pnl'] >= 0 else "📉"
    pnl_sign = "+" if stats['unrealized_pnl'] >= 0 else ""
    
    portfolio_msg = f"""💼 *Portfolio Overview*

💵 *Balance:*
  Total: ${stats['total_value']:,.2f}
  Available: ${stats['available']:,.2f}
  Locked: ${stats['locked']:,.2f}

📊 *Positions:*
  Open: {stats['position_count']}
  Value: ${stats['position_value']:,.2f}
  {pnl_emoji} P&L: {pnl_sign}${stats['unrealized_pnl']:,.2f}

📋 *Orders:*
  Active: {stats['open_orders']}

💹 *Current Price:*
  {settings.trading_symbol}: ${stats['current_price']:,.2f}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="portfolio"),
            InlineKeyboardButton("📈 Positions", callback_data="positions")
        ],
        [
            InlineKeyboardButton("📋 Orders", callback_data="orders"),
            InlineKeyboardButton("💵 Balance", callback_data="balance")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(portfolio_msg, reply_markup=reply_markup, parse_mode='Markdown')


async def positions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /positions command - show open positions"""
    # Get fresh settings
    settings = get_current_settings()
    
    await update.message.reply_text("📈 Loading positions...")
    
    positions = await data_fetcher.get_positions()
    price_data = await data_fetcher.get_current_price()
    current_price = price_data.get('price', 0)
    
    if not positions:
        positions_msg = f"""📈 *Open Positions*

No open positions

💹 Current Price: ${current_price:,.2f}
"""
    else:
        positions_msg = f"""📈 *Open Positions* ({len(positions)})\n\n"""
        
        for i, pos in enumerate(positions[:10], 1):  # Limit to 10
            if isinstance(pos, dict):
                size = float(pos.get('size', 0))
                entry_price = float(pos.get('entry_price', 0))
                side = "🟢 LONG" if size > 0 else "🔴 SHORT"
                
                pnl = size * (current_price - entry_price)
                pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                pnl_emoji = "📈" if pnl >= 0 else "📉"
                
                positions_msg += f"""*Position #{i}*
{side} {abs(size)} {settings.trading_symbol}
Entry: ${entry_price:,.2f}
Current: ${current_price:,.2f}
{pnl_emoji} P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)

"""
    
    positions_msg += f"🕐 {datetime.now().strftime('%H:%M:%S')}"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="positions")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(positions_msg, reply_markup=reply_markup, parse_mode='Markdown')


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command - show account balance"""
    await update.message.reply_text("💵 Loading balance...")
    
    balance = await data_fetcher.get_balance()
    
    if 'error' in balance:
        await update.message.reply_text(f"❌ Error: {balance['error']}")
        return
    
    balance_msg = f"""💵 *Account Balance*

💰 Total: ${balance['total']:,.2f} {balance['currency']}
✅ Available: ${balance['available']:,.2f}
🔒 Locked: ${balance['locked']:,.2f}

📊 Utilization: {(balance['locked'] / balance['total'] * 100) if balance['total'] > 0 else 0:.1f}%

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="balance"),
            InlineKeyboardButton("💼 Portfolio", callback_data="portfolio")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(balance_msg, reply_markup=reply_markup, parse_mode='Markdown')


async def orders_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /orders command - show active orders"""
    await update.message.reply_text("📋 Loading active orders...")
    
    orders = await data_fetcher.get_active_orders()
    
    if not orders:
        orders_msg = f"""📋 *Active Orders*

No active orders

🕐 {datetime.now().strftime('%H:%M:%S')}
"""
    else:
        orders_msg = f"""📋 *Active Orders* ({len(orders)})\n\n"""
        
        for i, order in enumerate(orders[:10], 1):  # Limit to 10
            if isinstance(order, dict):
                side = order.get('side', 'UNKNOWN')
                order_type = order.get('type', 'LIMIT')
                size = float(order.get('size', 0))
                price = float(order.get('price', 0))
                filled = float(order.get('filled', 0))
                
                side_emoji = "🟢" if side == "BUY" else "🔴"
                
                orders_msg += f"""*Order #{i}*
{side_emoji} {side} {order_type}
Size: {size} (Filled: {filled})
Price: ${price:,.2f}

"""
    
    orders_msg += f"🕐 {datetime.now().strftime('%H:%M:%S')}"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="orders")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(orders_msg, reply_markup=reply_markup, parse_mode='Markdown')


async def trades_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trades command - show recent trades"""
    await update.message.reply_text("🔄 Loading recent trades...")
    
    trades = await data_fetcher.get_recent_trades(limit=5)
    
    if not trades:
        trades_msg = f"""🔄 *Recent Trades*

No recent trades found

🕐 {datetime.now().strftime('%H:%M:%S')}
"""
    else:
        trades_msg = f"""🔄 *Recent Market Trades* (Last {len(trades)})\n\n"""
        
        for i, trade in enumerate(trades, 1):
            if isinstance(trade, dict):
                price = float(trade.get('price', 0))
                size = float(trade.get('size', 0))
                side = trade.get('side', 'UNKNOWN')
                timestamp = trade.get('timestamp', 0)
                
                side_emoji = "🟢" if side == "BUY" else "🔴"
                
                # Format timestamp if available
                time_str = ""
                if timestamp:
                    try:
                        dt = datetime.fromtimestamp(int(timestamp) / 1000)
                        time_str = dt.strftime('%H:%M:%S')
                    except:
                        time_str = "N/A"
                
                trades_msg += f"""{side_emoji} {side} {size} @ ${price:,.2f}
{time_str}

"""
    
    trades_msg += f"🕐 {datetime.now().strftime('%H:%M:%S')}"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="trades")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(trades_msg, reply_markup=reply_markup, parse_mode='Markdown')


def main():
    """Start the Telegram bot"""
    # Get token from environment
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN not set in .env")
        print("Get your token from @BotFather on Telegram")
        sys.exit(1)
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("start_bot", start_bot_cmd))
    application.add_handler(CommandHandler("stop_bot", stop_bot_cmd))
    application.add_handler(CommandHandler("restart_bot", restart_bot_cmd))
    application.add_handler(CommandHandler("status", status_cmd))
    application.add_handler(CommandHandler("logs", logs_cmd))
    application.add_handler(CommandHandler("config", config_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    
    # Trading data commands
    if TRADING_MODULES_AVAILABLE:
        application.add_handler(CommandHandler("price", price_cmd))
        application.add_handler(CommandHandler("portfolio", portfolio_cmd))
        application.add_handler(CommandHandler("positions", positions_cmd))
        application.add_handler(CommandHandler("balance", balance_cmd))
        application.add_handler(CommandHandler("orders", orders_cmd))
        application.add_handler(CommandHandler("trades", trades_cmd))
    
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start bot
    print("🤖 Telegram Bot Controller started!")
    print(f"📍 Controlling bot at: {os.path.dirname(os.path.abspath(__file__))}")
    print("✅ Send /start to your bot on Telegram to begin")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
