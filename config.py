"""
Configuration management for Lighter trading bot
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Bot configuration settings"""
    
    # API Configuration
    lighter_base_url: str = Field(default="https://mainnet.zklighter.elliot.ai", env="LIGHTER_BASE_URL")
    lighter_ws_url: str = Field(default="wss://mainnet.zklighter.elliot.ai/ws", env="LIGHTER_WS_URL")
    lighter_api_key_private_key: str = Field(env="LIGHTER_API_KEY_PRIVATE_KEY")
    lighter_account_index: int = Field(env="LIGHTER_ACCOUNT_INDEX")
    lighter_api_key_index: int = Field(default=2, env="LIGHTER_API_KEY_INDEX")
    lighter_eth_private_key: Optional[str] = Field(default=None, env="LIGHTER_ETH_PRIVATE_KEY")
    
    # Trading Configuration
    trading_symbol: str = Field(default="BTC-PERP", env="TRADING_SYMBOL")
    trading_market_id: int = Field(default=0, env="TRADING_MARKET_ID")
    max_position_size: float = Field(default=0.01, env="MAX_POSITION_SIZE")
    max_leverage: int = Field(default=10, env="MAX_LEVERAGE")
    max_daily_drawdown: float = Field(default=0.05, env="MAX_DAILY_DRAWDOWN")
    min_order_size: float = Field(default=0.001, env="MIN_ORDER_SIZE")
    
    # Risk Management
    liquidation_threshold: float = Field(default=0.8, env="LIQUIDATION_THRESHOLD")
    max_open_orders: int = Field(default=10, env="MAX_OPEN_ORDERS")
    position_check_interval: int = Field(default=60, env="POSITION_CHECK_INTERVAL")
    
    # Strategy Configuration
    enable_momentum_strategy: bool = Field(default=True, env="ENABLE_MOMENTUM_STRATEGY")
    enable_mean_reversion_strategy: bool = Field(default=True, env="ENABLE_MEAN_REVERSION_STRATEGY")
    enable_market_making_strategy: bool = Field(default=False, env="ENABLE_MARKET_MAKING_STRATEGY")
    enable_grid_trading_strategy: bool = Field(default=False, env="ENABLE_GRID_TRADING_STRATEGY")
    enable_orderflow_strategy: bool = Field(default=True, env="ENABLE_ORDERFLOW_STRATEGY")
    enable_sentiment_strategy: bool = Field(default=True, env="ENABLE_SENTIMENT_STRATEGY")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/bot.log", env="LOG_FILE")
    alert_webhook_url: Optional[str] = Field(default=None, env="ALERT_WEBHOOK_URL")
    
    # Environment
    environment: str = Field(default="mainnet", env="ENVIRONMENT")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
