"""
Configuration management for Lighter trading bot
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Bot configuration settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # API Configuration
    lighter_base_url: str = Field(default="https://mainnet.zklighter.elliot.ai", validation_alias="LIGHTER_BASE_URL")
    lighter_ws_url: str = Field(default="wss://mainnet.zklighter.elliot.ai/ws", validation_alias="LIGHTER_WS_URL")
    lighter_api_key_private_key: str = Field(validation_alias="LIGHTER_API_KEY_PRIVATE_KEY")
    lighter_account_index: int = Field(validation_alias="LIGHTER_ACCOUNT_INDEX")
    lighter_api_key_index: int = Field(default=2, validation_alias="LIGHTER_API_KEY_INDEX")
    lighter_eth_private_key: Optional[str] = Field(default=None, validation_alias="LIGHTER_ETH_PRIVATE_KEY")
    
    # Trading Configuration
    trading_symbol: str = Field(default="BTC-PERP", validation_alias="TRADING_SYMBOL")
    trading_market_id: int = Field(default=1, validation_alias="TRADING_MARKET_ID")
    max_position_size: float = Field(default=0.01, validation_alias="MAX_POSITION_SIZE")
    max_leverage: int = Field(default=10, validation_alias="MAX_LEVERAGE")
    max_daily_drawdown: float = Field(default=0.05, validation_alias="MAX_DAILY_DRAWDOWN")
    min_order_size: float = Field(default=0.001, validation_alias="MIN_ORDER_SIZE")
    
    # Risk Management
    liquidation_threshold: float = Field(default=0.8, validation_alias="LIQUIDATION_THRESHOLD")
    max_open_orders: int = Field(default=10, validation_alias="MAX_OPEN_ORDERS")
    position_check_interval: int = Field(default=60, validation_alias="POSITION_CHECK_INTERVAL")
    
    # Percentage-based Position Sizing
    position_size_percent: int = Field(default=7, validation_alias="POSITION_SIZE_PERCENT")  # REDUCED from 10% to 7%
    leverage: int = Field(default=5, validation_alias="LEVERAGE")  # 5x for 1m scalping
    stop_loss_percent: float = Field(default=2.0, validation_alias="STOP_LOSS_PERCENT")
    max_collateral: int = Field(default=12, validation_alias="MAX_COLLATERAL")  # REDUCED from 14% to 12% (12% × 5x = 60% max usage)
    max_open_positions: int = Field(default=3, validation_alias="MAX_OPEN_POSITIONS")  # REDUCED from 5 to 3
    
    # Static Scaled Profit Taking (3 levels)
    profit_taking_mode: str = Field(default="scaled", validation_alias="PROFIT_TAKING_MODE")
    profit_level_1_percent: float = Field(default=2.0, validation_alias="PROFIT_LEVEL_1_PERCENT")
    profit_level_1_size: int = Field(default=40, validation_alias="PROFIT_LEVEL_1_SIZE")
    profit_level_2_percent: float = Field(default=3.0, validation_alias="PROFIT_LEVEL_2_PERCENT")
    profit_level_2_size: int = Field(default=30, validation_alias="PROFIT_LEVEL_2_SIZE")
    profit_level_3_percent: float = Field(default=4.0, validation_alias="PROFIT_LEVEL_3_PERCENT")
    profit_level_3_size: int = Field(default=30, validation_alias="PROFIT_LEVEL_3_SIZE")
    
    # Strategy Configuration - ENABLE ALL FOR MAXIMUM ACCURACY
    aggressive_mode: bool = Field(default=True, validation_alias="AGGRESSIVE_MODE")
    enable_momentum_strategy: bool = Field(default=True, validation_alias="ENABLE_MOMENTUM_STRATEGY")
    enable_mean_reversion_strategy: bool = Field(default=True, validation_alias="ENABLE_MEAN_REVERSION_STRATEGY")
    enable_market_making_strategy: bool = Field(default=False, validation_alias="ENABLE_MARKET_MAKING_STRATEGY")  # Not for directional trading
    enable_grid_trading_strategy: bool = Field(default=False, validation_alias="ENABLE_GRID_TRADING_STRATEGY")  # Not for directional trading
    enable_orderflow_strategy: bool = Field(default=True, validation_alias="ENABLE_ORDERFLOW_STRATEGY")
    enable_sentiment_strategy: bool = Field(default=False, validation_alias="ENABLE_SENTIMENT_STRATEGY")  # Requires API keys
    
    # Time-of-Day Filter (avoid low liquidity hours)
    trading_hours_start: int = Field(default=6, validation_alias="TRADING_HOURS_START")  # 6am UTC
    trading_hours_end: int = Field(default=3, validation_alias="TRADING_HOURS_END")  # 3am UTC (next day)
    enable_time_filter: bool = Field(default=True, validation_alias="ENABLE_TIME_FILTER")
    
    # API & Network Configuration
    api_retry_limit: int = Field(default=3, validation_alias="API_RETRY_LIMIT")
    api_timeout: int = Field(default=30, validation_alias="API_TIMEOUT")
    api_initial_delay: float = Field(default=1.0, validation_alias="API_INITIAL_DELAY")
    api_max_delay: float = Field(default=30.0, validation_alias="API_MAX_DELAY")
    
    # Resilience - Circuit Breaker
    cb_failure_threshold: int = Field(default=5, validation_alias="CB_FAILURE_THRESHOLD")
    cb_reset_timeout: float = Field(default=60.0, validation_alias="CB_RESET_TIMEOUT")
    cb_half_open_max_calls: int = Field(default=1, validation_alias="CB_HALF_OPEN_MAX_CALLS")
    
    # Safety Configuration
    dry_run: bool = Field(default=False, validation_alias="DRY_RUN")
    use_testnet: bool = Field(default=False, validation_alias="USE_TESTNET")
    
    # Logging
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")  # Changed from DEBUG to INFO for production
    log_file: str = Field(default="logs/bot.log", validation_alias="LOG_FILE")
    alert_webhook_url: Optional[str] = Field(default=None, validation_alias="ALERT_WEBHOOK_URL")
    
    # Environment
    environment: str = Field(default="mainnet", validation_alias="ENVIRONMENT")

    # Validators for sanity checks
    @field_validator("max_leverage")
    @classmethod
    def _validate_leverage(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("MAX_LEVERAGE must be between 1 and 100")
        return v

    @field_validator("max_daily_drawdown")
    @classmethod
    def _validate_drawdown(cls, v: float) -> float:
        if v <= 0 or v >= 1:
            raise ValueError("MAX_DAILY_DRAWDOWN must be between 0 and 1 (e.g., 0.05)")
        return v

    @field_validator("min_order_size")
    @classmethod
    def _validate_min_order_size(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("MIN_ORDER_SIZE must be greater than 0")
        return v

    @field_validator("cb_failure_threshold")
    @classmethod
    def _validate_cb_threshold(cls, v: int) -> int:
        if v < 1:
            raise ValueError("CB_FAILURE_THRESHOLD must be >= 1")
        return v

    @field_validator("cb_reset_timeout")
    @classmethod
    def _validate_cb_timeout(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("CB_RESET_TIMEOUT must be > 0 seconds")
        return v


# Global settings instance
settings = Settings()
