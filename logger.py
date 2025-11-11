"""
Logging and monitoring system for the trading bot
"""
import logging
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import requests
from config import settings


class BotLogger:
    """Centralized logging for trading bot"""
    
    def __init__(self, log_file: str = None, log_level: str = None):
        self.log_file = log_file or settings.log_file
        self.log_level = log_level or settings.log_level
        
        # Create logs directory if it doesn't exist
        log_dir = Path(self.log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logger
        self.logger = logging.getLogger("LighterBot")
        self.logger.setLevel(getattr(logging, self.log_level.upper()))
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # File handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(getattr(logging, self.log_level.upper()))
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)
        
        # Structured log file for trades/orders
        self.trade_log_file = str(Path(log_dir) / "trades.jsonl")
        self.position_log_file = str(Path(log_dir) / "positions.jsonl")
        self.error_log_file = str(Path(log_dir) / "errors.jsonl")
    
    def _write_jsonl(self, filepath: str, data: Dict[str, Any]):
        """Write data to JSONL file"""
        try:
            with open(filepath, 'a') as f:
                json.dump(data, f)
                f.write('\n')
        except Exception as e:
            self.logger.error(f"Error writing to {filepath}: {e}")
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False):
        """Log error message"""
        self.logger.error(message, exc_info=exc_info)
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)
    
    def log_order(self, order_data: Dict[str, Any], action: str = "placed"):
        """
        Log order details
        
        Args:
            order_data: Order information
            action: Action taken (placed, filled, cancelled)
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "order",
            "action": action,
            "data": order_data
        }
        
        self._write_jsonl(self.trade_log_file, log_entry)
        
        # Also log to main logger
        order_id = order_data.get("order_id", "unknown")
        symbol = order_data.get("symbol", "unknown")
        side = order_data.get("side", "unknown")
        size = order_data.get("size", 0)
        
        self.info(f"Order {action}: {order_id} - {side} {size} {symbol}")
    
    def log_fill(self, fill_data: Dict[str, Any]):
        """
        Log order fill
        
        Args:
            fill_data: Fill/execution information
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "fill",
            "data": fill_data
        }
        
        self._write_jsonl(self.trade_log_file, log_entry)
        
        symbol = fill_data.get("symbol", "unknown")
        side = fill_data.get("side", "unknown")
        size = fill_data.get("size", 0)
        price = fill_data.get("price", 0)
        
        self.info(f"Order filled: {side} {size} {symbol} @ {price}")
    
    def log_position(self, position_data: Dict[str, Any], action: str = "update"):
        """
        Log position update
        
        Args:
            position_data: Position information
            action: Action (opened, closed, update)
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "position",
            "action": action,
            "data": position_data
        }
        
        self._write_jsonl(self.position_log_file, log_entry)
        
        symbol = position_data.get("symbol", "unknown")
        size = position_data.get("size", 0)
        unrealized_pnl = position_data.get("unrealized_pnl", 0)
        
        self.info(f"Position {action}: {symbol} size={size} PnL={unrealized_pnl:.2f}")
    
    def log_error(self, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """
        Log error with context
        
        Args:
            error_type: Type of error
            error_message: Error message
            context: Additional context
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "error",
            "error_type": error_type,
            "message": error_message,
            "context": context or {}
        }
        
        self._write_jsonl(self.error_log_file, log_entry)
        self.error(f"{error_type}: {error_message}")
    
    def log_strategy_signal(self, strategy_name: str, signal_data: Dict[str, Any]):
        """Log strategy signal"""
        self.info(
            f"Strategy {strategy_name}: {signal_data.get('action', 'unknown')} - "
            f"{signal_data.get('reason', 'no reason')}"
        )
    
    def log_risk_alert(self, alert_type: str, message: str, metrics: Dict[str, Any] = None):
        """Log risk management alert"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "risk_alert",
            "alert_type": alert_type,
            "message": message,
            "metrics": metrics or {}
        }
        
        self._write_jsonl(self.error_log_file, log_entry)
        self.warning(f"Risk Alert [{alert_type}]: {message}")


class AlertManager:
    """Alert manager for sending notifications"""
    
    def __init__(self, logger: BotLogger, webhook_url: Optional[str] = None):
        self.logger = logger
        self.webhook_url = webhook_url or settings.alert_webhook_url
        
        # Alert throttling to prevent spam
        self.last_alert_times: Dict[str, datetime] = {}
        self.alert_cooldown = 300  # 5 minutes
    
    def _should_send_alert(self, alert_key: str) -> bool:
        """Check if alert should be sent (throttling)"""
        if alert_key not in self.last_alert_times:
            return True
        
        time_since_last = (datetime.now() - self.last_alert_times[alert_key]).total_seconds()
        return time_since_last >= self.alert_cooldown
    
    def _send_webhook(self, message: str, level: str = "INFO"):
        """Send alert via webhook (Telegram Bot API)"""
        if not self.webhook_url:
            return
        
        try:
            # Extract bot token and chat ID from settings or webhook URL
            from config import settings
            bot_token = getattr(settings, 'telegram_bot_token', None)
            chat_id = getattr(settings, 'telegram_chat_id', None)
            
            if not bot_token or not chat_id:
                self.logger.debug("Telegram credentials not configured, skipping alert")
                return
            
            # Format message with emoji based on level
            level_emojis = {
                "INFO": "ℹ️",
                "WARNING": "⚠️",
                "ERROR": "❌",
                "CRITICAL": "🚨"
            }
            emoji = level_emojis.get(level, "ℹ️")
            
            formatted_message = f"{emoji} *{level}*\n\n{message}\n\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Send via Telegram Bot API
            telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": formatted_message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            response = requests.post(
                telegram_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            
        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {e}")
    
    def send_alert(self, message: str, level: str = "INFO", alert_key: Optional[str] = None):
        """
        Send alert notification
        
        Args:
            message: Alert message
            level: Alert level (INFO, WARNING, ERROR, CRITICAL)
            alert_key: Key for throttling (alerts with same key are throttled)
        """
        # Use message as key if no key provided
        key = alert_key or message
        
        # Check throttling
        if not self._should_send_alert(key):
            return
        
        # Send alert
        self._send_webhook(message, level)
        self.logger.info(f"Alert sent: {message}")
        
        # Update last alert time
        self.last_alert_times[key] = datetime.now()
    
    def alert_order_filled(self, order_data: Dict[str, Any]):
        """Alert when order is filled"""
        symbol = order_data.get("symbol", "unknown")
        side = order_data.get("side", "unknown")
        size = order_data.get("size", 0)
        price = order_data.get("price", 0)
        
        message = f"Order filled: {side} {size} {symbol} @ {price}"
        self.send_alert(message, "INFO", alert_key=f"fill_{symbol}")
    
    def alert_position_opened(self, position_data: Dict[str, Any]):
        """Alert when position is opened"""
        symbol = position_data.get("symbol", "unknown")
        size = position_data.get("size", 0)
        entry_price = position_data.get("entry_price", 0)
        
        message = f"Position opened: {size} {symbol} @ {entry_price}"
        self.send_alert(message, "INFO", alert_key=f"position_open_{symbol}")
    
    def alert_position_closed(self, position_data: Dict[str, Any], pnl: float):
        """Alert when position is closed"""
        symbol = position_data.get("symbol", "unknown")
        
        pnl_text = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        message = f"Position closed: {symbol} PnL: {pnl_text}"
        
        level = "INFO" if pnl >= 0 else "WARNING"
        self.send_alert(message, level, alert_key=f"position_close_{symbol}")
    
    def alert_high_risk(self, risk_type: str, message: str):
        """Alert for high risk situations"""
        self.send_alert(f"HIGH RISK - {risk_type}: {message}", "WARNING", alert_key=risk_type)
    
    def alert_emergency(self, message: str):
        """Alert for emergency situations"""
        self.send_alert(f"EMERGENCY: {message}", "CRITICAL", alert_key=None)
    
    def alert_error(self, error_message: str):
        """Alert for errors"""
        self.send_alert(f"Error: {error_message}", "ERROR", alert_key="error")
    
    def alert_daily_summary(self, summary: Dict[str, Any]):
        """Send daily performance summary"""
        total_pnl = summary.get("total_pnl", 0)
        num_trades = summary.get("num_trades", 0)
        win_rate = summary.get("win_rate", 0)
        
        pnl_text = f"+${total_pnl:.2f}" if total_pnl >= 0 else f"-${abs(total_pnl):.2f}"
        
        message = (
            f"Daily Summary: PnL: {pnl_text} | "
            f"Trades: {num_trades} | Win Rate: {win_rate:.1%}"
        )
        
        level = "INFO" if total_pnl >= 0 else "WARNING"
        self.send_alert(message, level, alert_key="daily_summary")


# Global logger and alert manager instances
_logger: Optional[BotLogger] = None
_alert_manager: Optional[AlertManager] = None


def get_logger() -> BotLogger:
    """Get global logger instance"""
    global _logger
    if _logger is None:
        _logger = BotLogger()
    return _logger


def get_alert_manager() -> AlertManager:
    """Get global alert manager instance"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager(get_logger())
    return _alert_manager


# Create default logger instance for imports
logger = get_logger().logger
