"""
Telegram Bot Controller for Lighter Trading Bot
Allows remote control and monitoring via Telegram
"""
import asyncio
import os
import signal
import subprocess
import sys
from datetime import datetime
from typing import Optional
import psutil

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from config import settings
from logger import logger


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
            asyncio.sleep(2)
            
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
            os.kill(self.bot_pid, signal.SIGTERM)
            
            # Wait for process to terminate
            for _ in range(10):
                if not self.is_running():
                    # Clean up PID file
                    if os.path.exists('data/bot.pid'):
                        os.remove('data/bot.pid')
                    return True, "✅ Bot stopped successfully!"
                asyncio.sleep(1)
            
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
        # Stop first
        success, msg = self.stop_bot()
        if not success and "not running" not in msg.lower():
            return False, msg
        
        # Wait a moment
        asyncio.sleep(2)
        
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
                with open('logs/bot.log', 'r') as f:
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
            with open('logs/bot.log', 'r') as f:
                all_lines = f.readlines()
                recent = all_lines[-lines:] if len(all_lines) >= lines else all_lines
                return "".join(recent)
        except Exception as e:
            return f"Error reading logs: {str(e)}"


# Global controller instance
controller = TradingBotController()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
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
            InlineKeyboardButton("📝 Logs", callback_data="logs"),
            InlineKeyboardButton("⚙️ Config", callback_data="config")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_msg = f"""🤖 *Lighter Trading Bot Controller*

Welcome! Use the buttons below to control your trading bot.

Current Status: {"✅ RUNNING" if controller.is_running() else "❌ STOPPED"}

Network: {settings.lighter_base_url.split('//')[1].split('.')[0].upper()}
Market: {settings.trading_symbol}
DRY_RUN: {settings.dry_run}
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
        await config_cmd(query, context)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """🤖 *Bot Commands*

/start - Show main control panel
/start_bot - Start the trading bot
/stop_bot - Stop the trading bot
/restart_bot - Restart the trading bot
/status - Show bot status
/logs - Show recent logs
/config - Show configuration
/help - Show this help message

💡 *Tips:*
• Use buttons for easy control
• Check status regularly
• Review logs for errors
• Start with testnet first
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')


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
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start bot
    print("🤖 Telegram Bot Controller started!")
    print(f"📍 Controlling bot at: {os.path.dirname(os.path.abspath(__file__))}")
    print("✅ Send /start to your bot on Telegram to begin")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
