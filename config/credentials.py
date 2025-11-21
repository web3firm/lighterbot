"""
Credentials Manager - Centralized configuration loading
Loads and validates all environment variables
"""

import os
import logging
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env file
load_dotenv()


class Credentials:
    """Centralized credentials and configuration"""
    
    def __init__(self):
        """Load and validate all credentials"""
        # Lighter Protocol
        self.lighter_api_url = os.getenv('LIGHTER_API_URL', 'https://api.lighter.xyz/v1')
        self.lighter_private_key = os.getenv('LIGHTER_PRIVATE_KEY')
        self.lighter_account_address = os.getenv('LIGHTER_ACCOUNT_ADDRESS')
        self.lighter_testnet = os.getenv('LIGHTER_TESTNET', 'false').lower() == 'true'
        
        # Trading configuration
        self.symbol = os.getenv('SYMBOL', 'BTC-USD')
        self.bot_mode = os.getenv('BOT_MODE', 'rule_based')
        self.max_leverage = int(os.getenv('MAX_LEVERAGE', '5'))
        self.position_size_pct = float(os.getenv('POSITION_SIZE_PCT', '0.8'))
        self.max_positions = int(os.getenv('MAX_POSITIONS', '2'))
        self.stop_loss_pct = float(os.getenv('STOP_LOSS_PCT', '5.0'))
        self.take_profit_pct = float(os.getenv('TAKE_PROFIT_PCT', '15.0'))
        
        # Risk management
        self.max_daily_loss_pct = float(os.getenv('MAX_DAILY_LOSS_PCT', '5.0'))
        self.max_drawdown_pct = float(os.getenv('MAX_DRAWDOWN_PCT', '10.0'))
        self.max_position_size_pct = float(os.getenv('MAX_POSITION_SIZE_PCT', '70.0'))
        
        # Telegram
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Database
        self.database_url = os.getenv('DATABASE_URL')
        
        # ML configuration
        self.ml_enabled = os.getenv('ML_ENABLED', 'true').lower() == 'true'
        self.ml_min_trades = int(os.getenv('ML_MIN_TRADES', '1000'))
        self.ml_auto_train = os.getenv('ML_AUTO_TRAIN', 'true').lower() == 'true'
        self.ml_retrain_interval = int(os.getenv('ML_RETRAIN_INTERVAL', '86400'))
        
        # Logging
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.log_to_file = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
        self.log_dir = Path(os.getenv('LOG_DIR', 'logs'))
        
        # Advanced
        self.loop_interval = float(os.getenv('LOOP_INTERVAL', '1.0'))
        self.close_positions_on_shutdown = os.getenv('CLOSE_POSITIONS_ON_SHUTDOWN', 'true').lower() == 'true'
        
        # Validate
        self._validate()
    
    def _validate(self):
        """Validate critical credentials"""
        errors = []
        
        if not self.lighter_private_key:
            errors.append("LIGHTER_PRIVATE_KEY not set")
        
        if not self.lighter_account_address:
            errors.append("LIGHTER_ACCOUNT_ADDRESS not set")
        
        if not self.telegram_bot_token:
            errors.append("TELEGRAM_BOT_TOKEN not set (required for notifications)")
        
        if not self.telegram_chat_id:
            errors.append("TELEGRAM_CHAT_ID not set (required for notifications)")
        
        if errors:
            raise ValueError(f"Missing credentials: {', '.join(errors)}")
        
        logger.info("✅ Credentials validated successfully")
    
    def get_lighter_config(self) -> dict:
        """Get Lighter Protocol configuration"""
        return {
            'api_url': self.lighter_api_url,
            'private_key': self.lighter_private_key,
            'account_address': self.lighter_account_address,
            'testnet': self.lighter_testnet
        }
    
    def get_trading_config(self) -> dict:
        """Get trading configuration"""
        return {
            'symbol': self.symbol,
            'bot_mode': self.bot_mode,
            'max_leverage': self.max_leverage,
            'position_size_pct': self.position_size_pct,
            'max_positions': self.max_positions,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct
        }
    
    def get_risk_config(self) -> dict:
        """Get risk management configuration"""
        return {
            'max_daily_loss_pct': self.max_daily_loss_pct,
            'max_drawdown_pct': self.max_drawdown_pct,
            'max_position_size_pct': self.max_position_size_pct
        }
    
    def get_telegram_config(self) -> dict:
        """Get Telegram configuration"""
        return {
            'bot_token': self.telegram_bot_token,
            'chat_id': self.telegram_chat_id
        }
    
    def get_database_url(self) -> Optional[str]:
        """Get database URL"""
        return self.database_url
    
    def get_ml_config(self) -> dict:
        """Get ML configuration"""
        return {
            'enabled': self.ml_enabled,
            'min_trades': self.ml_min_trades,
            'auto_train': self.ml_auto_train,
            'retrain_interval': self.ml_retrain_interval
        }


# Global credentials instance
_credentials: Optional[Credentials] = None


def get_credentials() -> Credentials:
    """Get or create global credentials instance"""
    global _credentials
    if _credentials is None:
        _credentials = Credentials()
    return _credentials


if __name__ == "__main__":
    # Test credentials loading
    try:
        creds = get_credentials()
        print("✅ Credentials loaded successfully")
        print(f"   Symbol: {creds.symbol}")
        print(f"   Leverage: {creds.max_leverage}x")
        print(f"   Position Size: {creds.position_size_pct}%")
        print(f"   ML Enabled: {creds.ml_enabled}")
        print(f"   ML Min Trades: {creds.ml_min_trades}")
    except Exception as e:
        print(f"❌ Failed to load credentials: {e}")
