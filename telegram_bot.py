"""
🚀 ULTRA-ADVANCED TELEGRAM BOT FOR LIGHTERBOT
================================

Professional trading bot interface with:
- Emergency stop/start controls
- Advanced position management
- Portfolio dashboard with charts
- Live logs monitoring
- Multi-asset trading
- Risk management controls
- Modern UI with inline keyboards
"""

import os
import sys
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add current directory to path to import local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataclasses import dataclass
import subprocess
import psutil

from dotenv import load_dotenv, set_key
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode

load_dotenv()

from logger import logger, get_logger
from config import settings
from order_manager import OrderManager
from market_data import MarketData
from win_rate_tracker import win_rate_tracker
from profit_manager import profit_manager
from risk_manager import AdvancedRiskManager


@dataclass
class BotState:
    """Track bot operational state"""
    is_running: bool = False
    start_time: Optional[datetime] = None
    last_error: Optional[str] = None
    trades_today: int = 0
    pnl_today: float = 0.0


class UltraAdvancedTradingBot:
    """Ultra-Advanced Trading Bot Interface"""
    
    def __init__(self):
        self.order_manager = OrderManager()
        self.market_data = MarketData()
        self.risk_manager = AdvancedRiskManager(self.order_manager, self.market_data)
        self.bot_state = BotState()
        self.authorized_users = set()
        self.log_buffer = []
        self.max_log_buffer = 100
        
        # Available trading pairs
        self.available_pairs = {
            "ETH-PERP": {"market_id": 0, "symbol": "ETH", "name": "Ethereum"},
            "BTC-PERP": {"market_id": 1, "symbol": "BTC", "name": "Bitcoin"},
            "SOL-PERP": {"market_id": 2, "symbol": "SOL", "name": "Solana"},
        }
        
    async def check_bot_process(self) -> Dict[str, Any]:
        """Check if main bot process is running"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                cmdline = proc.info.get('cmdline', [])
                if any('main.py' in cmd for cmd in cmdline):
                    return {
                        'running': True,
                        'pid': proc.info['pid'],
                        'memory': proc.memory_info().rss / 1024 / 1024,  # MB
                        'cpu': proc.cpu_percent(),
                        'uptime': datetime.now() - datetime.fromtimestamp(proc.create_time())
                    }
            return {'running': False}
        except Exception as e:
            return {'running': False, 'error': str(e)}
    
    async def start_bot(self) -> bool:
        """Start the trading bot process"""
        try:
            subprocess.Popen([
                sys.executable, '/root/lighterbot/main.py'
            ], cwd='/root/lighterbot')
            await asyncio.sleep(2)  # Wait for startup
            return True
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            return False
    
    async def stop_bot(self) -> bool:
        """Stop the trading bot process"""
        try:
            subprocess.run(['pkill', '-f', 'main.py'], check=False)
            await asyncio.sleep(1)  # Wait for shutdown
            return True
        except Exception as e:
            logger.error(f"Failed to stop bot: {e}")
            return False
    
    async def get_portfolio_stats(self) -> Dict[str, Any]:
        """Get comprehensive portfolio statistics"""
        try:
            account = await self.order_manager.get_account_info()
            positions = await self.order_manager.get_positions()
            stats = win_rate_tracker.get_statistics()
            
            # Calculate portfolio metrics
            total_value = 0
            unrealized_pnl = 0
            position_count = 0
            
            for pos in positions:
                if hasattr(pos, 'is_open') and pos.is_open:
                    position_count += 1
                    unrealized_pnl += getattr(pos, 'unrealized_pnl', 0)
                    total_value += abs(getattr(pos, 'size', 0) * getattr(pos, 'mark_price', 0))
            
            if isinstance(account, dict):
                if 'accounts' in account and len(account['accounts']) > 0:
                    acc_data = account['accounts'][0]
                    collateral = float(acc_data.get('collateral', 0))
                    available = float(acc_data.get('available_collateral', 0))
                else:
                    collateral = float(account.get('collateral', 0))
                    available = float(account.get('available_collateral', 0))
            else:
                collateral = available = 0
            
            return {
                'total_collateral': collateral,
                'available_collateral': available,
                'used_collateral': collateral - available,
                'unrealized_pnl': unrealized_pnl,
                'position_count': position_count,
                'total_position_value': total_value,
                'win_rate': stats.get('win_rate', 0),
                'total_trades': stats.get('total_trades', 0),
                'avg_pnl': stats.get('avg_pnl_percent', 0),
                'portfolio_heat': total_value / collateral if collateral > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting portfolio stats: {e}")
            return {}
    
    async def get_recent_logs(self, level: str = "ALL", limit: int = 20) -> List[str]:
        """Get recent log entries"""
        try:
            log_file = Path("/root/lighterbot/bot.log")
            if not log_file.exists():
                return ["No log file found"]
            
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            # Filter by level if specified
            if level != "ALL":
                lines = [line for line in lines if level in line]
            
            # Return last N lines
            return lines[-limit:] if lines else ["No logs available"]
        except Exception as e:
            return [f"Error reading logs: {e}"]
    
    async def switch_trading_pair(self, pair_key: str) -> bool:
        """Switch trading pair"""
        try:
            if pair_key not in self.available_pairs:
                return False
            
            pair_info = self.available_pairs[pair_key]
            env_file = Path("/root/lighterbot/.env")
            
            # Update .env file
            set_key(env_file, "TRADING_MARKET_ID", str(pair_info["market_id"]))
            set_key(env_file, "TRADING_SYMBOL", pair_key)
            
            logger.info(f"Switched trading pair to {pair_key}")
            return True
        except Exception as e:
            logger.error(f"Error switching pair: {e}")
            return False


# Initialize bot interface
bot_interface = UltraAdvancedTradingBot()


# ================================
# COMMAND HANDLERS
# ================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced start command with main dashboard"""
    user_id = update.effective_user.id
    bot_interface.authorized_users.add(user_id)
    
    # Main dashboard keyboard
    keyboard = [
        [
            InlineKeyboardButton("🚀 Start Bot", callback_data="emergency_start"),
            InlineKeyboardButton("⛔ Stop Bot", callback_data="emergency_stop")
        ],
        [
            InlineKeyboardButton("📊 Portfolio", callback_data="portfolio"),
            InlineKeyboardButton("📈 Positions", callback_data="positions_advanced")
        ],
        [
            InlineKeyboardButton("🤖 Bot Status", callback_data="bot_status"),
            InlineKeyboardButton("📋 Live Logs", callback_data="logs_menu")
        ],
        [
            InlineKeyboardButton("🔄 Switch Pair", callback_data="switch_pair"),
            InlineKeyboardButton("⚙️ Settings", callback_data="advanced_settings")
        ],
        [
            InlineKeyboardButton("📚 Help", callback_data="help_advanced")
        ]
    ]
    
    welcome_msg = (
        "🚀 *ULTRABOT COMMAND CENTER*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 *Aggressive ETH Scalping*\n"
        f"• Trading: ETH-PERP\n"
        f"• Leverage: {settings.leverage}x\n"
        f"• Position Size: {settings.position_size_percent}%\n"
        f"• SL/TP: -{settings.stop_loss_percent}% / +{settings.profit_level_1_percent}%\n\n"
        "⚠️ *High Risk Mode Active*\n"
        "10x leveraged scalping for maximum gains.\n\n"
        "Choose an option below:"
    )
    
    await update.message.reply_text(
        welcome_msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def emergency_controls_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle emergency start/stop controls"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action == "emergency_start":
        # Confirmation dialog
        keyboard = [
            [
                InlineKeyboardButton("✅ CONFIRM START", callback_data="confirm_start"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]
        ]
        msg = (
            "🚀 *EMERGENCY START*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ *WARNING*\n"
            "This will start live trading with real funds.\n\n"
            "Current Settings:\n"
            f"• Symbol: `{settings.trading_symbol}`\n"
            f"• Market ID: `{settings.trading_market_id}`\n"
            f"• Position Size: `{settings.position_size_percent}%`\n"
            f"• Leverage: `{settings.leverage}x`\n"
            f"• Stop Loss: `{settings.stop_loss_percent}%`\n\n"
            "🔥 *Confirm to start trading*"
        )
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif action == "emergency_stop":
        # Confirmation dialog
        keyboard = [
            [
                InlineKeyboardButton("🛑 CONFIRM STOP", callback_data="confirm_stop"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]
        ]
        msg = (
            "⛔ *EMERGENCY STOP*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ *WARNING*\n"
            "This will immediately stop the trading bot.\n"
            "Open positions will NOT be closed automatically.\n\n"
            "🔥 *Confirm to stop trading*"
        )
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif action == "confirm_start":
        success = await bot_interface.start_bot()
        if success:
            msg = (
                "🚀 *BOT STARTED SUCCESSFULLY*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "✅ Trading bot is now active\n"
                "📊 Monitoring markets\n"
                "⚡ Ready for opportunities\n\n"
                "Use /status to monitor progress"
            )
        else:
            msg = (
                "❌ *FAILED TO START BOT*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Please check logs for errors\n"
                "Try manual restart if needed"
            )
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
    
    elif action == "confirm_stop":
        success = await bot_interface.stop_bot()
        if success:
            msg = (
                "⛔ *BOT STOPPED SUCCESSFULLY*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "✅ Trading bot is now inactive\n"
                "📊 Positions remain open\n"
                "⚡ Ready for manual restart\n\n"
                "Use emergency start to resume"
            )
        else:
            msg = (
                "❌ *FAILED TO STOP BOT*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Please check manually\n"
                "Bot may still be running"
            )
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)


async def portfolio_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced portfolio dashboard"""
    query = update.callback_query
    await query.answer()
    
    stats = await bot_interface.get_portfolio_stats()
    
    if not stats:
        await query.edit_message_text("❌ Unable to fetch portfolio data")
        return
    
    # Risk level emoji
    heat = stats.get('portfolio_heat', 0)
    if heat < 0.3:
        risk_emoji = "🟢"
        risk_text = "LOW"
    elif heat < 0.7:
        risk_emoji = "🟡"
        risk_text = "MEDIUM"
    else:
        risk_emoji = "🔴"
        risk_text = "HIGH"
    
    # PnL emoji
    pnl = stats.get('unrealized_pnl', 0)
    pnl_emoji = "📈" if pnl >= 0 else "📉"
    
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="portfolio"),
            InlineKeyboardButton("📊 Details", callback_data="portfolio_details")
        ],
        [
            InlineKeyboardButton("📈 P&L Chart", callback_data="pnl_chart"),
            InlineKeyboardButton("⚖️ Risk Analysis", callback_data="risk_analysis")
        ],
        [
            InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
        ]
    ]
    
    msg = (
        "💼 *PORTFOLIO DASHBOARD*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 *Balance*\n"
        f"Total: `${stats.get('total_collateral', 0):.2f}`\n"
        f"Available: `${stats.get('available_collateral', 0):.2f}`\n"
        f"Used: `${stats.get('used_collateral', 0):.2f}`\n\n"
        f"{pnl_emoji} *Unrealized PnL*\n"
        f"Amount: `${pnl:+.2f}`\n\n"
        f"📊 *Positions*\n"
        f"Open: `{stats.get('position_count', 0)}`\n"
        f"Value: `${stats.get('total_position_value', 0):.2f}`\n\n"
        f"{risk_emoji} *Risk Level*\n"
        f"Status: `{risk_text}`\n"
        f"Heat: `{heat:.1%}`\n\n"
        f"🎯 *Performance*\n"
        f"Win Rate: `{stats.get('win_rate', 0):.1%}`\n"
        f"Trades: `{stats.get('total_trades', 0)}`\n"
        f"Avg PnL: `{stats.get('avg_pnl', 0):.2%}`"
    )
    
    await query.edit_message_text(
        msg, 
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def positions_advanced_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced positions view with management options"""
    query = update.callback_query
    await query.answer()
    
    try:
        positions = await bot_interface.order_manager.get_positions()
        
        if not positions or not any(hasattr(pos, 'is_open') and pos.is_open for pos in positions):
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="positions_advanced")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            msg = (
                "📈 *POSITIONS*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "🚫 No open positions\n\n"
                "The bot will open positions when\n"
                "profitable opportunities are detected."
            )
            await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        # Build positions display
        msg = "📈 *ACTIVE POSITIONS*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        keyboard = []
        
        for pos in positions:
            if hasattr(pos, 'is_open') and pos.is_open:
                symbol = settings.trading_symbol
                direction = "🟢 LONG" if getattr(pos, 'is_long', True) else "🔴 SHORT"
                pnl = getattr(pos, 'unrealized_pnl', 0)
                pnl_pct = getattr(pos, 'pnl_percentage', 0)
                pnl_emoji = "📈" if pnl >= 0 else "📉"
                
                msg += (
                    f"{direction} {symbol}\n"
                    f"Size: `{abs(getattr(pos, 'size', 0)):.4f}`\n"
                    f"Entry: `${getattr(pos, 'entry_price', 0):.2f}`\n"
                    f"Mark: `${getattr(pos, 'mark_price', 0):.2f}`\n"
                    f"{pnl_emoji} PnL: `{pnl_pct:+.2f}%` (`${pnl:+.2f}`)\n\n"
                )
                
                # Add close button for each position
                keyboard.append([
                    InlineKeyboardButton(
                        f"❌ Close {symbol}",
                        callback_data=f"close_pos_{getattr(pos, 'market_id', 0)}"
                    )
                ])
        
        # Add control buttons
        keyboard.extend([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="positions_advanced"),
                InlineKeyboardButton("❌ Close All", callback_data="close_all_confirm")
            ],
            [
                InlineKeyboardButton("📊 P&L Details", callback_data="pnl_details"),
                InlineKeyboardButton("⚖️ Risk Check", callback_data="position_risk")
            ],
            [
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
            ]
        ])
        
        await query.edit_message_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error fetching positions: {e}")


async def bot_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced bot status monitoring"""
    query = update.callback_query
    await query.answer()
    
    # Check bot process status
    process_info = await bot_interface.check_bot_process()
    
    # Get system info
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
    except:
        cpu_percent = memory = disk = None
    
    # Status emoji
    if process_info.get('running'):
        status_emoji = "🟢"
        status_text = "ONLINE"
    else:
        status_emoji = "🔴"
        status_text = "OFFLINE"
    
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="bot_status"),
            InlineKeyboardButton("📊 Strategies", callback_data="strategy_status")
        ],
        [
            InlineKeyboardButton("⚡ Performance", callback_data="performance_metrics"),
            InlineKeyboardButton("🔧 Health Check", callback_data="health_check")
        ],
        [
            InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
        ]
    ]
    
    msg = (
        f"🤖 *BOT STATUS*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{status_emoji} *Status: {status_text}*\n\n"
    )
    
    if process_info.get('running'):
        uptime = process_info.get('uptime', timedelta(0))
        msg += (
            f"⏱️ *Runtime*\n"
            f"Uptime: `{str(uptime).split('.')[0]}`\n"
            f"PID: `{process_info.get('pid', 'N/A')}`\n\n"
            f"💾 *Resources*\n"
            f"Memory: `{process_info.get('memory', 0):.1f} MB`\n"
            f"CPU: `{process_info.get('cpu', 0):.1f}%`\n\n"
        )
    
    if memory:
        msg += (
            f"🖥️ *System*\n"
            f"CPU: `{cpu_percent:.1f}%`\n"
            f"RAM: `{memory.percent:.1f}%`\n"
            f"Disk: `{disk.percent:.1f}%`\n\n"
        )
    
    # Trading info
    msg += (
        f"📊 *Trading*\n"
        f"Symbol: `{settings.trading_symbol}`\n"
        f"Market ID: `{settings.trading_market_id}`\n"
        f"Mode: `{'AGGRESSIVE' if settings.aggressive_mode else 'CONSERVATIVE'}`\n"
        f"Position Size: `{settings.position_size_percent}%`"
    )
    
    await query.edit_message_text(
        msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def logs_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Live logs monitoring menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [
            InlineKeyboardButton("📋 All Logs", callback_data="logs_all"),
            InlineKeyboardButton("⚠️ Warnings", callback_data="logs_warning")
        ],
        [
            InlineKeyboardButton("❌ Errors", callback_data="logs_error"),
            InlineKeyboardButton("ℹ️ Info", callback_data="logs_info")
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="logs_menu"),
            InlineKeyboardButton("📥 Download", callback_data="logs_download")
        ],
        [
            InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
        ]
    ]
    
    msg = (
        "📋 *LIVE LOGS MONITOR*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 *Log Categories*\n"
        "• All Logs - Complete log output\n"
        "• Warnings - Important notices\n"
        "• Errors - Critical issues\n"
        "• Info - General information\n\n"
        "🔄 *Auto-refresh every 30s*\n"
        "Select a category to view:"
    )
    
    await query.edit_message_text(
        msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def close_position_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close specific position"""
    query = update.callback_query
    await query.answer()
    
    market_id = int(query.data.replace("close_pos_", ""))
    
    try:
        success = await bot_interface.order_manager.close_position_by_market_id(market_id)
        if success:
            msg = "✅ *Position Closed Successfully*\n\nThe position has been closed at market price."
        else:
            msg = "❌ *Failed to Close Position*\n\nPlease try again or close manually."
        
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
        
        # Auto-refresh positions after 2 seconds
        await asyncio.sleep(2)
        await positions_advanced_callback(update, context)
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def portfolio_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed portfolio information"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get detailed account info
        account_info = await bot_interface.order_manager.get_account_info()
        if not account_info:
            await query.edit_message_text("❌ *Error getting portfolio details*")
            return
        
        # Extract account details
        if isinstance(account_info, dict):
            if 'accounts' in account_info and len(account_info['accounts']) > 0:
                account = account_info['accounts'][0]
            else:
                account = account_info
        else:
            account = account_info
        
        total_collateral = float(account.get('collateral', 0))
        available_collateral = float(account.get('available_collateral', 0))
        used_collateral = total_collateral - available_collateral
        
        # Get position details
        positions = await bot_interface.order_manager.get_all_positions()
        open_positions = [pos for pos in positions if pos.is_open]
        
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in open_positions)
        
        msg = (
            f"📊 *PORTFOLIO DETAILS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 *Total Balance:* ${total_collateral:.2f}\n"
            f"✅ *Available:* ${available_collateral:.2f}\n"
            f"⚠️ *Used Margin:* ${used_collateral:.2f}\n"
            f"📈 *Unrealized PnL:* ${total_unrealized_pnl:+.2f}\n\n"
            f"📊 *Margin Usage:* {(used_collateral/total_collateral*100):.1f}%\n"
            f"🎯 *Open Positions:* {len(open_positions)}\n\n"
            f"💡 *Portfolio Health:*\n"
        )
        
        # Portfolio health analysis
        margin_usage = used_collateral / total_collateral if total_collateral > 0 else 0
        if margin_usage < 0.3:
            msg += f"🟢 Conservative ({margin_usage:.1%})\n"
        elif margin_usage < 0.6:
            msg += f"🟡 Moderate ({margin_usage:.1%})\n"
        else:
            msg += f"🔴 High Risk ({margin_usage:.1%})\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="portfolio_details")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def pnl_chart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show P&L chart and analysis"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get trading history for P&L analysis
        from win_rate_tracker import win_rate_tracker
        stats = win_rate_tracker.get_statistics()
        
        msg = (
            f"📈 *P&L ANALYSIS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 *Total PnL:* ${stats.get('total_pnl', 0):.2f}\n"
            f"🎯 *Win Rate:* {stats.get('win_rate', 0):.1f}%\n"
            f"📊 *Total Trades:* {stats.get('total_trades', 0)}\n"
            f"🟢 *Winners:* {stats.get('winners', 0)}\n"
            f"🔴 *Losers:* {stats.get('losers', 0)}\n"
            f"⚡ *Profit Factor:* {stats.get('profit_factor', 0):.2f}\n\n"
            f"📈 *Average Win:* ${stats.get('avg_win', 0):.2f}\n"
            f"📉 *Average Loss:* ${stats.get('avg_loss', 0):.2f}\n"
        )
        
        # Add performance analysis
        if stats.get('total_trades', 0) > 0:
            win_rate = stats.get('win_rate', 0)
            if win_rate >= 70:
                msg += f"\n🎉 *Excellent Performance!*\n"
            elif win_rate >= 50:
                msg += f"\n👍 *Good Performance*\n"
            else:
                msg += f"\n⚠️ *Needs Improvement*\n"
        else:
            msg += f"\n📊 *No trading history available*\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="pnl_chart")],
            [InlineKeyboardButton("📊 Portfolio", callback_data="portfolio")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def risk_analysis_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show risk analysis and metrics"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get risk metrics
        portfolio_heat = await bot_interface.risk_manager.calculate_portfolio_heat()
        max_drawdown = bot_interface.risk_manager.max_drawdown_today
        win_rate = bot_interface.risk_manager.win_rate
        kelly_fraction = bot_interface.risk_manager.calculate_kelly_size()
        
        # Get account info for risk calculations
        account_info = await bot_interface.order_manager.get_account_info()
        positions = await bot_interface.order_manager.get_all_positions()
        open_positions = [pos for pos in positions if pos.is_open]
        
        msg = (
            f"⚖️ *RISK ANALYSIS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔥 *Portfolio Heat:* {portfolio_heat:.1%}\n"
            f"📉 *Max Drawdown Today:* {max_drawdown:.1%}\n"
            f"🎯 *Win Rate:* {win_rate:.1%}\n"
            f"🧮 *Kelly Fraction:* {kelly_fraction:.2f}\n\n"
            f"📊 *Current Exposure:*\n"
            f"   Open Positions: {len(open_positions)}\n"
            f"   Max Allowed: {settings.max_open_positions}\n\n"
            f"💡 *Risk Level:*\n"
        )
        
        # Risk level assessment
        if portfolio_heat < 0.3 and len(open_positions) <= 2:
            msg += f"   🟢 *Low Risk* - Conservative trading\n"
        elif portfolio_heat < 0.6 and len(open_positions) <= 4:
            msg += f"   🟡 *Medium Risk* - Balanced approach\n"
        else:
            msg += f"   🔴 *High Risk* - Aggressive trading\n"
        
        msg += f"\n⚠️ *Safety Limits:*\n"
        msg += f"   • Max Drawdown: {settings.max_daily_drawdown:.1%}\n"
        msg += f"   • Stop Loss: {settings.stop_loss_percent:.1%}\n"
        msg += f"   • Position Size: {settings.position_size_percent:.0f}%\n"
        msg += f"   • Max Positions: {settings.max_open_positions}\n"
        msg += f"   • Leverage: {settings.max_leverage}x\n\n"
        msg += f"💡 *Recommendations:*\n"
        
        if portfolio_heat > 0.7:
            msg += f"   ⚠️ Consider reducing exposure\n"
        if max_drawdown > 0.03:
            msg += f"   ⚠️ High drawdown - tighten stops\n"
        if win_rate < 0.5:
            msg += f"   ⚠️ Win rate below 50% - review strategy\n"
        if len(open_positions) == 0:
            msg += f"   ℹ️ No open positions - waiting for opportunities\n"
        
        if portfolio_heat < 0.3 and win_rate > 0.6:
            msg += f"   ✅ Good risk/reward balance\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="risk_analysis")],
            [InlineKeyboardButton("📊 Portfolio", callback_data="portfolio")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def advanced_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current bot settings"""
    query = update.callback_query
    await query.answer()
    
    try:
        msg = (
            f"⚙️ *BOT SETTINGS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 *Trading Mode:*\n"
            f"   {settings.trading_symbol}\n"
            f"   Market ID: {settings.trading_market_id}\n\n"
            f"💰 *Position Sizing:*\n"
            f"   Size per trade: {settings.position_size_percent:.0f}%\n"
            f"   Leverage: {settings.max_leverage}x\n"
            f"   Max collateral: {settings.max_collateral}%\n"
            f"   Max positions: {settings.max_open_positions}\n\n"
            f"🛡️ *Risk Management:*\n"
            f"   Stop loss: {settings.stop_loss_percent:.1f}%\n"
            f"   Max daily drawdown: {settings.max_daily_drawdown:.1%}\n\n"
            f"📈 *Profit Taking:*\n"
            f"   Level 1: {settings.profit_level_1_percent}% ({settings.profit_level_1_size}%)\n"
            f"   Level 2: {settings.profit_level_2_percent}% ({settings.profit_level_2_size}%)\n"
            f"   Level 3: {settings.profit_level_3_percent}% ({settings.profit_level_3_size}%)\n\n"
            f"🔧 *System:*\n"
            f"   Mode: {'🟢 LIVE' if not settings.dry_run else '🔵 DRY RUN'}\n"
            f"   Network: {'MAINNET' if 'mainnet' in settings.lighter_base_url else 'TESTNET'}\n"
            f"   Aggressive: {'✅ ON' if settings.aggressive_mode else '❌ OFF'}\n"
            f"   Log level: {settings.log_level}\n\n"
            f"⚠️ *To change settings:*\n"
            f"   Edit `.env` file and restart bot\n"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="advanced_settings")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def portfolio_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed portfolio breakdown"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Get account info
        account_info = await bot_interface.order_manager.get_account_info()
        positions = await bot_interface.order_manager.get_all_positions()
        
        # Parse account data
        if isinstance(account_info, dict):
            if 'accounts' in account_info and len(account_info['accounts']) > 0:
                acc_data = account_info['accounts'][0]
                balance = float(acc_data.get('collateral', 0))
                available = float(acc_data.get('available_collateral', 0))
                used_collateral = balance - available
            else:
                balance = float(account_info.get('collateral', 0))
                available = float(account_info.get('available_collateral', 0))
                used_collateral = balance - available
        else:
            balance = available = used_collateral = 0.0
        
        # Calculate position breakdown
        open_positions = [pos for pos in positions if pos.is_open]
        total_pnl = sum(pos.unrealized_pnl for pos in open_positions if pos.unrealized_pnl)
        long_positions = [pos for pos in open_positions if pos.is_long]
        short_positions = [pos for pos in open_positions if not pos.is_long]
        
        msg = (
            f"📊 *PORTFOLIO DETAILS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 *Capital Allocation:*\n"
            f"   Total Balance: ${balance:.2f}\n"
            f"   Available: ${available:.2f}\n"
            f"   Used: ${used_collateral:.2f}\n"
            f"   Utilization: {(used_collateral/balance*100 if balance > 0 else 0):.1f}%\n\n"
            f"📈 *Positions Summary:*\n"
            f"   Total: {len(open_positions)}\n"
            f"   Long: {len(long_positions)}\n"
            f"   Short: {len(short_positions)}\n"
            f"   Total P&L: ${total_pnl:.2f}\n\n"
            f"🎯 *Position Breakdown:*\n"
        )
        
        if open_positions:
            for pos in open_positions[:5]:  # Show first 5 positions
                pnl_emoji = "🟢" if pos.unrealized_pnl > 0 else "🔴"
                side_emoji = "📈" if pos.is_long else "📉"
                msg += (
                    f"\n{side_emoji} Market {pos.market_id}:\n"
                    f"   Size: {abs(pos.size):.4f}\n"
                    f"   Entry: ${pos.entry_price:.4f}\n"
                    f"   Current: ${pos.mark_price:.4f}\n"
                    f"   {pnl_emoji} P&L: ${pos.unrealized_pnl:.2f} ({pos.pnl_percentage:+.2f}%)\n"
                )
            
            if len(open_positions) > 5:
                msg += f"\n... and {len(open_positions) - 5} more positions\n"
        else:
            msg += f"   No open positions\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="portfolio_details")],
            [InlineKeyboardButton("📊 Simple View", callback_data="portfolio")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def advanced_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show advanced settings menu"""
    query = update.callback_query
    await query.answer()
    
    try:
        msg = (
            f"⚙️ *ADVANCED SETTINGS*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 *Current Configuration:*\n"
            f"   Trading Mode: {'🔴 LIVE' if not settings.dry_run else '🟡 DRY RUN'}\n"
            f"   Position Size: {settings.position_size_percent}%\n"
            f"   Leverage: {settings.leverage}x\n"
            f"   Stop Loss: {settings.stop_loss_percent}%\n"
            f"   Max Positions: {settings.max_open_positions}\n"
            f"   Max Drawdown: {settings.max_daily_drawdown*100:.1f}%\n\n"
            f"🚀 *Ultra-Dynamic Scanner:*\n"
            f"   Status: {'✅ ACTIVE' if ultra_scanner.initialized else '❌ INACTIVE'}\n"
            f"   Markets: {len(ultra_scanner.available_markets) if ultra_scanner.initialized else 'N/A'}\n"
            f"   Top 10 Mode: ✅ ENABLED\n\n"
            f"💡 *Settings are configured via .env file*\n"
            f"📝 Restart bot to apply changes\n"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="advanced_settings")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information"""
    query = update.callback_query
    await query.answer()
    
    try:
        msg = (
            f"📚 *HELP & DOCUMENTATION*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🤖 *Bot Overview:*\n"
            f"   • Ultra-Dynamic Top 10 Volume Scanner\n"
            f"   • Automatic market discovery\n"
            f"   • Real-time opportunity detection\n"
            f"   • Advanced risk management\n\n"
            f"📊 *Key Features:*\n"
            f"   • Portfolio tracking\n"
            f"   • Position management\n"
            f"   • P&L analysis\n"
            f"   • Risk monitoring\n"
            f"   • Live logging\n\n"
            f"🎯 *Commands:*\n"
            f"   /start - Main menu\n"
            f"   /status - Bot status\n"
            f"   /help - This help\n\n"
            f"⚠️ *Important:*\n"
            f"   • Always monitor positions\n"
            f"   • Bot uses real funds on mainnet\n"
            f"   • Safety features active\n"
            f"   • Emergency stop available\n\n"
            f"📱 *Support:*\n"
            f"   Check bot logs for details\n"
            f"   Review .env configuration\n"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def ultra_dynamic_markets_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show real-time top 10 markets by volume"""
    query = update.callback_query
    await query.answer()
    
    try:
        if not ultra_scanner:
            await query.edit_message_text("❌ Ultra scanner not initialized")
            return
        
        # Get top 10 markets
        top_markets = ultra_scanner.top_10_markets
        
        if not top_markets:
            msg = (
                f"🔍 *ULTRA-DYNAMIC MARKETS*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⏳ Scanner initializing...\n"
                f"Please wait for first scan to complete\n"
            )
        else:
            msg = (
                f"🔥 *TOP 10 VOLUME MARKETS*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            )
            
            for i, market in enumerate(top_markets[:10], 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}️⃣"
                
                symbol = market.get('symbol', 'UNKNOWN')
                volume_24h = market.get('volume_24h', 0)
                price_change_24h = market.get('price_change_24h', 0)
                current_price = market.get('current_price', 0)
                
                change_emoji = "🟢" if price_change_24h > 0 else "🔴" if price_change_24h < 0 else "⚪"
                
                msg += (
                    f"{emoji} *{symbol}*\n"
                    f"   💵 ${current_price:.4f}\n"
                    f"   {change_emoji} {price_change_24h:+.2f}% (24h)\n"
                    f"   📊 Vol: ${volume_24h:,.0f}\n\n"
                )
            
            # Add scanner stats
            last_update = ultra_scanner.last_scan_time
            if last_update:
                import datetime
                time_ago = (datetime.datetime.now() - last_update).seconds
                msg += f"⏱️ *Updated:* {time_ago}s ago\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="ultra_markets")],
            [InlineKeyboardButton("📊 Portfolio", callback_data="portfolio")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information"""
    query = update.callback_query
    await query.answer()
    
    try:
        msg = (
            f"📚 *HELP & DOCUMENTATION*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🤖 *Bot Overview:*\n"
            f"   • Ultra-Dynamic Top 10 Volume Scanner\n"
            f"   • Automatic market discovery\n"
            f"   • Real-time opportunity detection\n"
            f"   • Advanced risk management\n\n"
            f"📊 *Key Features:*\n"
            f"   • Portfolio tracking\n"
            f"   • Position management\n"
            f"   • P&L analysis\n"
            f"   • Risk monitoring\n"
            f"   • Live logging\n\n"
            f"🎯 *Commands:*\n"
            f"   /start - Main menu\n"
            f"   /status - Bot status\n"
            f"   /help - This help\n\n"
            f"⚠️ *Important:*\n"
            f"   • Bot trades with REAL funds\n"
            f"   • Always monitor positions\n"
            f"   • Use emergency stop if needed\n"
            f"   • Settings in .env file\n\n"
            f"💡 *Need support?*\n"
            f"   Check logs for detailed info\n"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
        
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu callback from inline keyboard"""
    query = update.callback_query
    await query.answer()
    
    # Main dashboard keyboard
    keyboard = [
        [
            InlineKeyboardButton("🚀 Start Bot", callback_data="emergency_start"),
            InlineKeyboardButton("⛔ Stop Bot", callback_data="emergency_stop")
        ],
        [
            InlineKeyboardButton("📊 Portfolio", callback_data="portfolio"),
            InlineKeyboardButton("📈 Positions", callback_data="positions_advanced")
        ],
        [
            InlineKeyboardButton("🤖 Bot Status", callback_data="bot_status"),
            InlineKeyboardButton("📋 Live Logs", callback_data="logs_menu")
        ],
        [
            InlineKeyboardButton("🔄 Switch Pair", callback_data="switch_pair"),
            InlineKeyboardButton("⚙️ Settings", callback_data="advanced_settings")
        ],
        [
            InlineKeyboardButton("📚 Help", callback_data="help_advanced")
        ]
    ]
    
    welcome_msg = (
        "🚀 *ULTRABOT COMMAND CENTER*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 *Ultra-Dynamic Top 10 Volume Scanner*\n"
        "Advanced AI-powered trading bot\n\n"
        "✨ Choose an option below:"
    )
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(welcome_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


# ================================
# CALLBACK QUERY ROUTER
# ================================

async def advanced_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Advanced callback query handler"""
    query = update.callback_query
    data = query.data
    
    # Emergency controls
    if data in ["emergency_start", "emergency_stop", "confirm_start", "confirm_stop"]:
        await emergency_controls_callback(update, context)
    
    # Portfolio
    elif data == "portfolio":
        await portfolio_callback(update, context)
    
    # Positions
    elif data == "positions_advanced":
        await positions_advanced_callback(update, context)
    
    # Bot status
    elif data == "bot_status":
        await bot_status_callback(update, context)
    
    # Logs
    elif data == "logs_menu":
        await logs_menu_callback(update, context)
    elif data.startswith("logs_"):
        await logs_display_callback(update, context)
    
    # Position management
    elif data.startswith("close_pos_"):
        await close_position_callback(update, context)
    
    # Portfolio details
    elif data == "portfolio_details":
        await portfolio_details_callback(update, context)
    
    # PnL chart
    elif data == "pnl_chart":
        await pnl_chart_callback(update, context)
    
    # Risk analysis
    elif data == "risk_analysis":
        await risk_analysis_callback(update, context)
    
    # Advanced settings
    elif data == "advanced_settings":
        await advanced_settings_callback(update, context)
    
    # Ultra dynamic markets
    elif data == "ultra_markets":
        await ultra_dynamic_markets_callback(update, context)
    
    # Help
    elif data == "help_advanced":
        await help_callback(update, context)
    
    # Main menu
    elif data == "main_menu":
        await main_menu_callback(update, context)
    
    # Cancel
    elif data == "cancel":
        await query.edit_message_text("❌ *Operation Cancelled*", parse_mode=ParseMode.MARKDOWN)
    
    else:
        await query.answer("🚧 Feature coming soon!")


async def logs_display_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display filtered logs"""
    query = update.callback_query
    await query.answer()
    
    log_type = query.data.replace("logs_", "").upper()
    
    logs = await bot_interface.get_recent_logs(log_type, 15)
    
    if not logs:
        log_content = "No logs available"
    else:
        log_content = "\n".join(logs[-10:])  # Last 10 lines
        if len(log_content) > 3000:  # Telegram message limit
            log_content = log_content[-3000:] + "..."
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data=f"logs_{log_type.lower()}")],
        [InlineKeyboardButton("🏠 Logs Menu", callback_data="logs_menu")]
    ]
    
    msg = (
        f"📋 *{log_type} LOGS*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"```\n{log_content}\n```"
    )
    
    await query.edit_message_text(
        msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def set_pair_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set trading pair"""
    query = update.callback_query
    await query.answer()
    
    pair_key = query.data.replace("set_pair_", "")
    
    if pair_key == settings.trading_symbol:
        await query.edit_message_text(f"✅ Already trading {pair_key}")
        return
    
    # Confirmation
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm Switch", callback_data=f"confirm_switch_{pair_key}"),
            InlineKeyboardButton("❌ Cancel", callback_data="switch_pair")
        ]
    ]
    
    pair_info = bot_interface.available_pairs.get(pair_key, {})
    
    msg = (
        f"🔄 *SWITCH TO {pair_key}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *New Pair*\n"
        f"Symbol: `{pair_key}`\n"
        f"Name: `{pair_info.get('name', 'Unknown')}`\n"
        f"Market ID: `{pair_info.get('market_id', 'Unknown')}`\n\n"
        "⚠️ *Important*\n"
        "• Bot will be restarted\n"
        "• Close open positions first\n"
        "• Settings will be preserved\n\n"
        "Confirm the switch?"
    )
    
    await query.edit_message_text(
        msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def close_position_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close specific position"""
    query = update.callback_query
    await query.answer()
    
    market_id = int(query.data.replace("close_pos_", ""))
    
    try:
        success = await bot_interface.order_manager.close_position_by_market_id(market_id)
        if success:
            msg = "✅ *Position Closed Successfully*\n\nThe position has been closed at market price."
        else:
            msg = "❌ *Failed to Close Position*\n\nPlease try again or close manually."
        
        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)
        
        # Auto-refresh positions after 2 seconds
        await asyncio.sleep(2)
        await positions_advanced_callback(update, context)
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")


def main():
    """Start the Ultra-Advanced Telegram Bot"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not set")
        return
    
    print("🚀 Starting Ultra-Advanced Telegram Bot...")
    
    app = Application.builder().token(token).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", start_command))
    app.add_handler(CommandHandler("help", start_command))
    
    # Callback query handler
    app.add_handler(CallbackQueryHandler(advanced_callback_handler))
    
    # Error handler
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Log Errors caused by Updates."""
        logger.error(f"Update {update} caused error {context.error}")
    
    app.add_error_handler(error_handler)
    
    print("✅ Ultra-Advanced Bot is running...")
    print("📱 Send /start to begin")
    
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()