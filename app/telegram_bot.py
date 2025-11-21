"""
Telegram Bot - User interface and notifications
15 commands + inline buttons + real-time alerts
"""

import logging
import asyncio
import os
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters
)

logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Telegram bot for user interaction and notifications
    Provides trading controls and real-time updates
    """
    
    def __init__(self, bot_instance=None):
        """
        Initialize Telegram bot
        
        Args:
            bot_instance: Reference to main LighterBot instance
        """
        self.token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.bot_instance = bot_instance
        self.application: Optional[Application] = None
        
        # Notification settings
        self.notify_on_signals = True
        self.notify_on_trades = True
        self.notify_on_pnl_changes = True
        self.pnl_notify_threshold = Decimal('2.0')  # Notify on ±2% PnL
        
        if not self.token:
            logger.warning("⚠️  TELEGRAM_BOT_TOKEN not set, Telegram disabled")
        else:
            logger.info("📱 Telegram Bot initialized")
    
    async def start_bot(self):
        """Start Telegram bot"""
        if not self.token:
            logger.warning("⚠️  Telegram token not configured, skipping")
            return
        
        try:
            # Create application
            self.application = Application.builder().token(self.token).build()
            
            # Register command handlers
            self.application.add_handler(CommandHandler("start", self.cmd_start))
            self.application.add_handler(CommandHandler("stop", self.cmd_stop))
            self.application.add_handler(CommandHandler("status", self.cmd_status))
            self.application.add_handler(CommandHandler("positions", self.cmd_positions))
            self.application.add_handler(CommandHandler("trades", self.cmd_trades))
            self.application.add_handler(CommandHandler("pnl", self.cmd_pnl))
            self.application.add_handler(CommandHandler("stats", self.cmd_stats))
            self.application.add_handler(CommandHandler("logs", self.cmd_logs))
            self.application.add_handler(CommandHandler("analytics", self.cmd_analytics))
            self.application.add_handler(CommandHandler("dbstats", self.cmd_dbstats))
            self.application.add_handler(CommandHandler("train", self.cmd_train))
            self.application.add_handler(CommandHandler("mlstatus", self.cmd_mlstatus))
            self.application.add_handler(CommandHandler("risk", self.cmd_risk))
            self.application.add_handler(CommandHandler("config", self.cmd_config))
            self.application.add_handler(CommandHandler("help", self.cmd_help))
            
            # Register callback handlers for inline buttons
            self.application.add_handler(CallbackQueryHandler(self.handle_callback))
            
            # Start polling
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("✅ Telegram bot started")
            
            # Send startup notification
            await self.send_message("🤖 LighterBot started successfully!\nUse /help for commands.")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Telegram bot: {e}")
    
    async def stop_bot(self):
        """Stop Telegram bot"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("📴 Telegram bot stopped")
    
    # ============ COMMAND HANDLERS ============
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start trading"""
        await update.message.reply_text("🚀 Starting bot...")
        
        if self.bot_instance:
            if not self.bot_instance.running:
                asyncio.create_task(self.bot_instance.start())
                await update.message.reply_text("✅ Bot started successfully!")
            else:
                await update.message.reply_text("⚠️  Bot is already running")
    
    async def cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop trading"""
        await update.message.reply_text("🛑 Stopping bot...")
        
        if self.bot_instance:
            if self.bot_instance.running:
                await self.bot_instance.stop()
                await update.message.reply_text("✅ Bot stopped successfully!")
            else:
                await update.message.reply_text("⚠️  Bot is not running")
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get bot status"""
        if not self.bot_instance:
            await update.message.reply_text("❌ Bot instance not available")
            return
        
        # Build status message
        status = "running" if self.bot_instance.running else "stopped"
        runtime = (datetime.now(timezone.utc) - self.bot_instance.stats['start_time']).total_seconds() / 3600
        
        msg = f"🤖 **Bot Status**\n\n"
        msg += f"Status: {status.upper()}\n"
        msg += f"Runtime: {runtime:.2f} hours\n"
        msg += f"Loop cycles: {self.bot_instance.loop_count}\n"
        msg += f"Symbol: {self.bot_instance.symbol}\n\n"
        
        # Account info
        if self.bot_instance.account_state:
            equity = self.bot_instance.account_state.get('account_value', 0)
            msg += f"💰 Account Value: ${equity:.2f}\n"
        
        # Position info
        if self.bot_instance.current_position:
            pos = self.bot_instance.current_position
            msg += f"\n📊 Open Position:\n"
            msg += f"   {pos['side'].upper()} {pos['symbol']}\n"
            msg += f"   Entry: ${pos['entry_price']}\n"
            msg += f"   Size: {pos['size']}\n"
            msg += f"   Leverage: {pos['leverage']}x\n"
        else:
            msg += f"\n📊 No open positions\n"
        
        # ML status
        if self.bot_instance.auto_trainer:
            ml_active = self.bot_instance.auto_trainer.is_ml_active()
            ml_status = "V2 (Active)" if ml_active else "V1 (Collection)"
            msg += f"\n🤖 ML Phase: {ml_status}\n"
        
        # Inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("🚀 START", callback_data="start"),
                InlineKeyboardButton("🛑 STOP", callback_data="stop")
            ],
            [
                InlineKeyboardButton("📊 Positions", callback_data="positions"),
                InlineKeyboardButton("💰 PnL", callback_data="pnl")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get open positions"""
        if not self.bot_instance:
            await update.message.reply_text("❌ Bot instance not available")
            return
        
        if self.bot_instance.current_position:
            pos = self.bot_instance.current_position
            msg = f"📊 **Open Position**\n\n"
            msg += f"Symbol: {pos['symbol']}\n"
            msg += f"Side: {pos['side'].upper()}\n"
            msg += f"Entry: ${pos['entry_price']}\n"
            msg += f"SL: ${pos['sl_price']}\n"
            msg += f"TP: ${pos['tp_price']}\n"
            msg += f"Size: {pos['size']}\n"
            msg += f"Leverage: {pos['leverage']}x\n"
            msg += f"Strategy: {pos['strategy']}\n"
            msg += f"Opened: {pos['entry_time']}\n"
        else:
            msg = "📊 No open positions"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get recent trades"""
        try:
            from app.database.db_manager import get_db_manager
            
            db = get_db_manager()
            
            if not db or not db.pool:
                await update.message.reply_text("❌ Database not connected")
                return
            
            trades = await db.get_recent_trades(limit=5)
            
            if not trades:
                await update.message.reply_text("📊 No recent trades")
                return
            
            msg = f"📊 **Recent Trades** (Last 5)\n\n"
            
            for trade in trades:
                pnl_symbol = "✅" if trade.get('pnl_usd', 0) > 0 else "❌"
                msg += f"{pnl_symbol} {trade['symbol']} {trade['side'].upper()}\n"
                msg += f"   Strategy: {trade['strategy']}\n"
                msg += f"   PnL: ${trade.get('pnl_usd', 0):.2f} ({trade.get('pnl_pct', 0):.2f}%)\n"
                msg += f"   Entry: {trade['entry_time']}\n\n"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def cmd_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get PnL statistics"""
        try:
            from app.database.analytics import Analytics
            from app.database.db_manager import get_db_manager
            
            db = get_db_manager()
            if not db or not db.pool:
                await update.message.reply_text("❌ Database not connected")
                return
            
            analytics = Analytics(db)
            stats = await analytics.get_win_rate(days=30)
            
            if not stats:
                await update.message.reply_text("❌ No statistics available")
                return
            
            msg = f"💰 **PnL Statistics** (30 days)\n\n"
            msg += f"Total Trades: {stats['total_trades']}\n"
            msg += f"Win Rate: {stats['win_rate']:.2f}%\n"
            msg += f"Total PnL: ${stats['total_pnl']:.2f}\n"
            msg += f"Avg PnL: {stats['avg_pnl_pct']:.2f}%\n\n"
            msg += f"Winning Trades: {stats['winning_trades']}\n"
            msg += f"Avg Win: ${stats['avg_win']:.2f}\n"
            msg += f"Largest Win: ${stats['largest_win']:.2f}\n\n"
            msg += f"Losing Trades: {stats['losing_trades']}\n"
            msg += f"Avg Loss: ${stats['avg_loss']:.2f}\n"
            msg += f"Largest Loss: ${stats['largest_loss']:.2f}\n\n"
            msg += f"Profit Factor: {stats['profit_factor']:.2f}\n"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get bot statistics"""
        if not self.bot_instance:
            await update.message.reply_text("❌ Bot instance not available")
            return
        
        stats = self.bot_instance.stats
        
        msg = f"📊 **Bot Statistics**\n\n"
        msg += f"Signals Generated: {stats['signals_generated']}\n"
        msg += f"Signals Accepted: {stats['signals_accepted']}\n"
        msg += f"Signals Rejected: {stats['signals_rejected']}\n"
        msg += f"Positions Opened: {stats['positions_opened']}\n"
        msg += f"Positions Closed: {stats['positions_closed']}\n"
        
        acceptance_rate = (stats['signals_accepted'] / stats['signals_generated'] * 100) if stats['signals_generated'] > 0 else 0
        msg += f"\nAcceptance Rate: {acceptance_rate:.2f}%\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get recent log entries"""
        try:
            # Read last 20 lines from log file
            log_file = "bot.log"
            if not os.path.exists(log_file):
                log_file = "logs/lighterbot_" + datetime.now().strftime("%Y%m%d") + ".log"
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    last_lines = lines[-20:] if len(lines) > 20 else lines
                    log_text = ''.join(last_lines)
                
                await update.message.reply_text(f"```\n{log_text}\n```", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Log file not found")
        except Exception as e:
            await update.message.reply_text(f"❌ Error reading logs: {e}")
    
    async def cmd_analytics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get analytics report"""
        try:
            from app.database.analytics import Analytics
            from app.database.db_manager import get_db_manager
            
            db = get_db_manager()
            if not db or not db.pool:
                await update.message.reply_text("❌ Database not connected")
                return
            
            analytics = Analytics(db)
            report = await analytics.get_comprehensive_report(days=30)
            
            if not report:
                await update.message.reply_text("❌ No analytics data available")
                return
            
            msg = f"📈 **Analytics Report** (30 days)\n\n"
            
            # Win rate
            wr = report.get('win_rate', {})
            msg += f"**Win Rate**\n"
            msg += f"Total: {wr.get('total_trades', 0)} trades\n"
            msg += f"Rate: {wr.get('win_rate', 0):.2f}%\n"
            msg += f"PnL: ${wr.get('total_pnl', 0):.2f}\n\n"
            
            # Strategy performance
            msg += f"**Strategy Performance**\n"
            for strategy, perf in report.get('strategy_performance', {}).items():
                msg += f"   {strategy}: {perf.get('total_trades', 0)} trades, Win Rate: {perf.get('win_rate', 0):.2f}%\n"
            
            # ML performance
            ml = report.get('ml_performance', {})
            if ml.get('total_predictions', 0) > 0:
                msg += f"\n**ML Performance**\n"
                msg += f"Accuracy: {ml.get('accuracy', 0):.2f}%\n"
                msg += f"Predictions: {ml.get('total_predictions', 0)}\n"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def cmd_dbstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get database statistics"""
        try:
            from app.database.db_manager import get_db_manager
            
            db = get_db_manager()
            
            if not db or not db.pool:
                await update.message.reply_text("❌ Database not connected")
                return
            
            async with db.pool.acquire() as conn:
                trades_count = await conn.fetchval("SELECT COUNT(*) FROM trades")
                signals_count = await conn.fetchval("SELECT COUNT(*) FROM signals")
                positions_count = await conn.fetchval("SELECT COUNT(*) FROM positions WHERE status = 'open'")
            
            msg = f"🗄️ **Database Statistics**\n\n"
            msg += f"Total Trades: {trades_count}\n"
            msg += f"Total Signals: {signals_count}\n"
            msg += f"Open Positions: {positions_count}\n"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Database error: {e}")
    
    async def cmd_train(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manually trigger ML training"""
        if not self.bot_instance or not self.bot_instance.auto_trainer:
            await update.message.reply_text("❌ ML trainer not available")
            return
        
        await update.message.reply_text("🎓 Starting ML training...")
        
        result = self.bot_instance.auto_trainer.check_and_train()
        
        if result:
            msg = f"✅ **Training Complete**\n\n"
            msg += f"Status: {result.get('status')}\n"
            msg += f"Accuracy: {result.get('accuracy', 0):.2f}%\n"
            msg += f"Training samples: {result.get('samples', 0)}\n"
        else:
            msg = "⚠️  Training not performed (check trade count)"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def cmd_mlstatus(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get ML system status"""
        if not self.bot_instance or not self.bot_instance.auto_trainer:
            await update.message.reply_text("❌ ML trainer not available")
            return
        
        trainer = self.bot_instance.auto_trainer
        status = trainer.get_status()
        
        msg = f"🤖 **ML System Status**\n\n"
        msg += f"Phase: {status['phase']}\n"
        msg += f"Trade Count: {status['trade_count']}\n"
        msg += f"Progress: {status['progress_pct']:.1f}%\n"
        msg += f"Model Trained: {'Yes' if status['model_trained'] else 'No'}\n"
        
        if status.get('last_training_time'):
            msg += f"Last Training: {status['last_training_time']}\n"
        
        if status.get('accuracy'):
            msg += f"Accuracy: {status['accuracy']:.2f}%\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def cmd_risk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get risk status"""
        if not self.bot_instance or not self.bot_instance.risk_manager:
            await update.message.reply_text("❌ Risk manager not available")
            return
        
        risk_status = self.bot_instance.risk_manager.get_full_status()
        
        msg = f"🛡️ **Risk Status**\n\n"
        msg += f"Can Trade: {'✅ Yes' if risk_status['can_trade'] else '❌ No'}\n\n"
        
        # Kill switch
        ks = risk_status['kill_switch']
        msg += f"**Kill Switch**\n"
        msg += f"Triggered: {'🚨 YES' if ks['triggered'] else '✅ No'}\n"
        msg += f"Threshold: {ks['daily_loss_trigger_pct']:.1f}%\n\n"
        
        # Drawdown
        dd = risk_status['drawdown']
        msg += f"**Drawdown**\n"
        msg += f"Current: {dd['current_drawdown_pct']:.2f}%\n"
        msg += f"Max: {dd['max_drawdown_pct']:.2f}%\n"
        msg += f"Warning: {dd['warning_threshold_pct']:.1f}%\n"
        msg += f"Critical: {dd['critical_threshold_pct']:.1f}%\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def cmd_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get configuration info"""
        msg = f"⚙️ **Configuration**\n\n"
        msg += f"Symbol: {os.getenv('TRADING_SYMBOL', 'BTC-USD')}\n"
        msg += f"Max Leverage: {os.getenv('MAX_LEVERAGE', '5')}x\n"
        msg += f"Position Size: {os.getenv('POSITION_SIZE_PCT', '50')}%\n"
        msg += f"Max Positions: 2\n"
        msg += f"Kill Switch: -5% daily loss\n"
        msg += f"Max Drawdown: 10%\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message"""
        msg = f"🤖 **LighterBot Commands**\n\n"
        msg += f"/start - Start trading\n"
        msg += f"/stop - Stop trading\n"
        msg += f"/status - Bot status\n"
        msg += f"/positions - Open positions\n"
        msg += f"/trades - Recent trades\n"
        msg += f"/pnl - PnL statistics\n"
        msg += f"/stats - Bot statistics\n"
        msg += f"/logs - Recent logs\n"
        msg += f"/analytics - Analytics report\n"
        msg += f"/dbstats - Database stats\n"
        msg += f"/train - Trigger ML training\n"
        msg += f"/mlstatus - ML system status\n"
        msg += f"/risk - Risk status\n"
        msg += f"/config - Configuration\n"
        msg += f"/help - This message\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    # ============ CALLBACK HANDLERS ============
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "start":
            await self.cmd_start(update, context)
        elif query.data == "stop":
            await self.cmd_stop(update, context)
        elif query.data == "positions":
            await self.cmd_positions(update, context)
        elif query.data == "pnl":
            await self.cmd_pnl(update, context)
    
    # ============ NOTIFICATIONS ============
    
    async def send_message(self, message: str):
        """Send message to user"""
        if not self.application or not self.chat_id:
            return
        
        try:
            await self.application.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram message: {e}")
    
    async def notify_signal(self, signal: Dict[str, Any]):
        """Notify about new signal"""
        if not self.notify_on_signals:
            return
        
        msg = f"🎯 **Signal Generated**\n\n"
        msg += f"Strategy: {signal['strategy']}\n"
        msg += f"Side: {signal['side'].upper()}\n"
        msg += f"Symbol: {signal['symbol']}\n"
        msg += f"Entry: ${signal['entry_price']}\n"
        msg += f"Confidence: {signal['confidence']:.2%}\n"
        
        await self.send_message(msg)
    
    async def notify_position_opened(self, position: Dict[str, Any]):
        """Notify about position opened"""
        if not self.notify_on_trades:
            return
        
        msg = f"✅ **Position Opened**\n\n"
        msg += f"Symbol: {position['symbol']}\n"
        msg += f"Side: {position['side'].upper()}\n"
        msg += f"Entry: ${position['entry_price']}\n"
        msg += f"Size: {position['size']}\n"
        msg += f"Leverage: {position['leverage']}x\n"
        msg += f"Strategy: {position['strategy']}\n"
        
        await self.send_message(msg)
    
    async def notify_position_closed(self, position: Dict[str, Any], pnl: float):
        """Notify about position closed"""
        if not self.notify_on_trades:
            return
        
        pnl_symbol = "✅" if pnl > 0 else "❌"
        
        msg = f"{pnl_symbol} **Position Closed**\n\n"
        msg += f"Symbol: {position['symbol']}\n"
        msg += f"Side: {position['side'].upper()}\n"
        msg += f"PnL: ${pnl:.2f}\n"
        
        await self.send_message(msg)
    
    async def notify_pnl_change(self, pnl_pct: Decimal):
        """Notify about significant PnL change"""
        if not self.notify_on_pnl_changes:
            return
        
        if abs(pnl_pct) < self.pnl_notify_threshold:
            return
        
        symbol = "✅" if pnl_pct > 0 else "❌"
        
        msg = f"{symbol} **PnL Alert**\n\n"
        msg += f"Change: {pnl_pct:+.2f}%\n"
        
        await self.send_message(msg)
    
    async def notify_kill_switch(self):
        """Notify about kill switch trigger"""
        msg = f"🚨 **KILL SWITCH TRIGGERED**\n\n"
        msg += f"Trading has been stopped due to -5% daily loss.\n"
        msg += f"Manual intervention required.\n"
        
        await self.send_message(msg)
    
    async def notify_ml_training(self, result: Dict[str, Any]):
        """Notify about ML training completion"""
        msg = f"🎓 **ML Training Complete**\n\n"
        msg += f"Status: {result.get('status')}\n"
        msg += f"Accuracy: {result.get('accuracy', 0):.2f}%\n"
        msg += f"Samples: {result.get('samples', 0)}\n"
        
        if result.get('status') == 'V2 activated':
            msg += f"\n✨ ML predictions now active!\n"
        
        await self.send_message(msg)


if __name__ == "__main__":
    # Test Telegram bot
    async def test():
        bot = TelegramBot()
        await bot.start_bot()
        await asyncio.sleep(3600)  # Run for 1 hour
        await bot.stop_bot()
    
    asyncio.run(test())
