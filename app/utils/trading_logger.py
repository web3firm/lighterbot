"""
Trading Logger - Structured logging for trading operations
Logs to console and files (trade storage handled by DatabaseManager)
"""

import logging
import json
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path

# Setup root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal types"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class TradingLogger:
    """
    Enterprise trading logger with structured logging
    Logs to console and files (trade storage handled by DatabaseManager)
    """
    
    def __init__(self, log_dir: str = "logs", component_name: str = "LighterBot"):
        """
        Initialize trading logger
        
        Args:
            log_dir: Directory for log files
            component_name: Name of component
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.component_name = component_name
        self.logger = logging.getLogger(component_name)
        
        # Setup file handlers
        self._setup_file_handlers()
        
        self.logger.info(f"📝 Trading Logger initialized")
        self.logger.info(f"   Log directory: {self.log_dir}")
    
    def _setup_file_handlers(self):
        """Setup file handlers for different log levels"""
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        
        # Main log file
        main_log = self.log_dir / f"{self.component_name.lower()}_{date_str}.log"
        main_handler = logging.FileHandler(main_log)
        main_handler.setLevel(logging.INFO)
        main_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        self.logger.addHandler(main_handler)
        
        # Error log file
        error_log = self.log_dir / f"{self.component_name.lower()}_errors_{date_str}.log"
        error_handler = logging.FileHandler(error_log)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        self.logger.addHandler(error_handler)
    
    def log_trade_signal(self, strategy: str, symbol: str, signal_type: str,
                        strength: int, indicators: Dict[str, Any]):
        """
        Log trading signal
        
        Args:
            strategy: Strategy name
            symbol: Trading pair
            signal_type: 'buy' or 'sell'
            strength: Signal strength (0-10)
            indicators: Dict of indicator values
        """
        self.logger.info(f"📊 SIGNAL: {strategy} - {signal_type.upper()} {symbol}")
        self.logger.info(f"   Strength: {strength}/10")
        self.logger.info(f"   Indicators: {indicators}")
    
    def log_trade_entry(self, trade_data: Dict[str, Any]):
        """
        Log trade entry (to be saved to database by bot)
        This is now a placeholder - actual storage handled by DatabaseManager
        
        Args:
            trade_data: Complete trade data including entry, indicators, etc.
        """
        self.logger.info(f"📊 Trade entry prepared for database storage")
    
    def log_trade_exit(self, trade_data: Dict[str, Any]):
        """
        Log trade exit (to be saved to database by bot)
        This is now a placeholder - actual storage handled by DatabaseManager
        
        Args:
            trade_data: Complete exit data including PnL, exit price, etc.
        """
        self.logger.info(f"📊 Trade exit prepared for database storage")
    
    def log_order_placed(self, symbol: str, side: str, size: Decimal,
                        price: Decimal, order_id: Optional[str] = None):
        """Log order placement"""
        self.logger.info(f"📤 ORDER PLACED: {side.upper()} {size} {symbol} @ ${price}")
        if order_id:
            self.logger.info(f"   Order ID: {order_id}")
    
    def log_order_filled(self, symbol: str, side: str, size: Decimal,
                        fill_price: Decimal, order_id: Optional[str] = None):
        """Log order fill"""
        self.logger.info(f"✅ ORDER FILLED: {side.upper()} {size} {symbol} @ ${fill_price}")
        if order_id:
            self.logger.info(f"   Order ID: {order_id}")
    
    def log_position_opened(self, symbol: str, side: str, size: Decimal,
                           entry_price: Decimal, leverage: int):
        """Log position opening"""
        self.logger.info(f"🚀 POSITION OPENED: {side.upper()} {size} {symbol}")
        self.logger.info(f"   Entry: ${entry_price:.4f}")
        self.logger.info(f"   Leverage: {leverage}x")
    
    def log_position_closed(self, symbol: str, side: str, size: Decimal,
                           exit_price: Decimal, pnl: Decimal, pnl_pct: Decimal):
        """Log position closing"""
        pnl_emoji = "🟢" if pnl > 0 else "🔴"
        self.logger.info(f"{pnl_emoji} POSITION CLOSED: {side.upper()} {size} {symbol}")
        self.logger.info(f"   Exit: ${exit_price:.4f}")
        self.logger.info(f"   PnL: ${pnl:.2f} ({pnl_pct:+.2f}%)")
    
    def log_risk_check(self, check_type: str, passed: bool, details: Dict[str, Any]):
        """Log risk management check"""
        status = "✅ PASSED" if passed else "❌ FAILED"
        self.logger.info(f"🛡️  RISK CHECK: {check_type} - {status}")
        if not passed:
            self.logger.warning(f"   Details: {details}")
    
    def log_kill_switch_triggered(self, reason: str, current_loss_pct: float):
        """Log kill switch activation"""
        self.logger.error(f"🚨 KILL SWITCH TRIGGERED!")
        self.logger.error(f"   Reason: {reason}")
        self.logger.error(f"   Current Loss: {current_loss_pct:.2f}%")
    
    def log_ml_training(self, trade_count: int, accuracy: float, phase: str):
        """Log ML training event"""
        self.logger.info(f"🧠 ML TRAINING COMPLETE")
        self.logger.info(f"   Trade Count: {trade_count}")
        self.logger.info(f"   Accuracy: {accuracy:.2%}")
        self.logger.info(f"   Phase: {phase}")
    
    def log_ml_prediction(self, symbol: str, prediction: int, probability: float):
        """Log ML prediction"""
        self.logger.info(f"🔮 ML PREDICTION: {symbol}")
        self.logger.info(f"   Prediction: {'PROFITABLE' if prediction == 1 else 'UNPROFITABLE'}")
        self.logger.info(f"   Probability: {probability:.2%}")
    
    def log_account_update(self, account_value: float, pnl: float, pnl_pct: float):
        """Log account state update"""
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        self.logger.info(f"{pnl_emoji} Account Value: ${account_value:.2f} | PnL: ${pnl:.2f} ({pnl_pct:+.2f}%)")
    
    def log_error(self, error_type: str, error_msg: str, context: Optional[Dict[str, Any]] = None):
        """Log error with context"""
        self.logger.error(f"❌ ERROR: {error_type}")
        self.logger.error(f"   Message: {error_msg}")
        if context:
            self.logger.error(f"   Context: {context}")


# Global logger instance
_global_logger: Optional[TradingLogger] = None


def get_logger(component_name: str = "LighterBot") -> TradingLogger:
    """Get or create global logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = TradingLogger(component_name=component_name)
    return _global_logger


if __name__ == "__main__":
    # Test logger
    logger = get_logger("Test")
    
    logger.log_trade_signal(
        strategy="swing_trader",
        symbol="BTC-USD",
        signal_type="buy",
        strength=8,
        indicators={'rsi': 35, 'macd': 0.5}
    )
    
    logger.log_trade_entry({
        'symbol': 'BTC-USD',
        'strategy': 'swing_trader',
        'side': 'buy',
        'entry_price': 50000,
        'size': 0.001,
        'indicators': {'rsi': 35, 'macd': 0.5}
    })
    
    print("✅ Logger test complete - check logs/ directory")
