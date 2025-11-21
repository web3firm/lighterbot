"""
Trading Configuration Loader
Loads and validates trading configuration from YAML files
"""

import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


async def load_trading_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load trading configuration from YAML file
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
        
    Raises:
        FileNotFoundError: If config file not found
        yaml.YAMLError: If config file is invalid
    """
    if config_path is None:
        config_path = Path('config/trading_rules.yml')
    
    try:
        logger.info(f"Loading trading configuration from {config_path}")
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Validate configuration
        validated_config = await _validate_config(config)
        
        logger.info("✅ Trading configuration loaded and validated")
        return validated_config
        
    except FileNotFoundError:
        logger.error(f"❌ Configuration file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"❌ Invalid YAML configuration: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to load configuration: {e}")
        raise


async def _validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize configuration
    
    Args:
        config: Raw configuration dictionary
        
    Returns:
        Validated and normalized configuration
    """
    # Validate loop interval
    loop_interval = config.get('loop_interval', 1.0)
    if not isinstance(loop_interval, (int, float)) or loop_interval <= 0:
        raise ValueError("loop_interval must be a positive number")
    
    # Validate risk settings
    risk_config = config.get('risk', {})
    
    max_daily_loss_pct = risk_config.get('max_daily_loss_pct', 5.0)
    if not 0 < max_daily_loss_pct < 100:
        raise ValueError("max_daily_loss_pct must be between 0 and 100")
    
    max_drawdown_pct = risk_config.get('max_drawdown_pct', 10.0)
    if not 0 < max_drawdown_pct < 100:
        raise ValueError("max_drawdown_pct must be between 0 and 100")
    
    # Validate strategies
    strategies = config.get('strategies', {})
    if not strategies:
        logger.warning("⚠️ No trading strategies configured")
    
    # Ensure enabled strategies have valid allocations
    total_allocation = 0.0
    for strategy_name, strategy_config in strategies.items():
        if strategy_config.get('enabled', False):
            allocation = strategy_config.get('allocation', 0.0)
            total_allocation += allocation
    
    if total_allocation > 0 and not (0.99 <= total_allocation <= 1.01):
        logger.warning(f"⚠️ Total strategy allocation is {total_allocation:.2f}, expected 1.0")
    
    logger.debug("✅ Critical settings validation passed")
    return config


def get_strategy_config(config: Dict[str, Any], strategy_name: str) -> Dict[str, Any]:
    """Get configuration for a specific strategy"""
    return config.get('strategies', {}).get(strategy_name, {})


def get_risk_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Get risk management configuration"""
    return config.get('risk', {})


def get_execution_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Get execution configuration"""
    return config.get('execution', {})


def get_ml_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Get ML configuration"""
    return config.get('ml', {})


def get_monitoring_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Get monitoring configuration"""
    return config.get('monitoring', {})


if __name__ == "__main__":
    import asyncio
    
    async def test_config_loading():
        """Test configuration loading"""
        try:
            config = await load_trading_config()
            print("✅ Configuration loaded successfully")
            print(f"Loop interval: {config.get('loop_interval')}")
            print(f"Max daily loss: {config.get('risk', {}).get('max_daily_loss_pct')}%")
            print(f"Strategies: {list(config.get('strategies', {}).keys())}")
            print(f"ML enabled: {config.get('ml', {}).get('enabled')}")
        except Exception as e:
            print(f"❌ Configuration test failed: {e}")
    
    asyncio.run(test_config_loading())
