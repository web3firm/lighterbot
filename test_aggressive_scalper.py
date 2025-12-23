
import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
import os

# Set env vars for testing
os.environ['MAX_LEVERAGE'] = '20'
os.environ['TP_PNL_PCT'] = '20.0'
os.environ['SL_PNL_PCT'] = '50.0'
os.environ['POSITION_SIZE_PCT'] = '95.0'

from app.strategies.rule_based.aggressive_scalper import AggressiveScalperStrategy

@pytest.mark.asyncio
async def test_aggressive_scalper_signal():
    """Test aggressive scalper signal generation"""
    
    strategy = AggressiveScalperStrategy('ETH-USD')
    
    # Mock account state ($20 account)
    account_state = {
        'total_raw_usd': 20.0,
        'account_value': 20.0,  # Legacy field
        'collateral': 20.0,
        'available_balance': 20.0
    }
    
    # Mock market data (Strong upward momentum)
    market_data = {
        'mark_price': 3000.0,
        'indicators': {
            'price_change_5m': 0.05,  # +5% (very strong momentum)
            'price_change_1h': 0.10,
            'rsi': 60,  # Healthy bullish RSI
            'momentum': 0.05
        }
    }
    
    # Generate signal
    signal = await strategy.generate_signal(market_data, account_state)
    
    assert signal is not None, "Signal should be generated for strong momentum"
    assert signal['side'] == 'buy'
    assert signal['leverage'] == 20
    assert signal['symbol'] == 'ETH-USD'
    
    # Check checks targets
    # Entry: 3000
    # TP: +20% PnL -> +1% Price -> 3000 * 1.01 = 3030
    # SL: -50% PnL -> -2.5% Price -> 3000 * 0.975 = 2925
    assert signal['entry_price'] == 3000.0
    assert signal['tp_price'] == 3030.0
    assert signal['sl_price'] == 2925.0
    
    # Check position size
    # 95% of $20 = $19
    # Leveraged size: $19 * 20 = $380
    # Size in ETH: 380 / 3000 = 0.1266...
    expected_size_usd = 19.0 * 20
    expected_size_eth = expected_size_usd / 3000.0
    
    assert abs(signal['size'] - expected_size_eth) < 0.01

@pytest.mark.asyncio
async def test_cooldown():
    """Test cooldown logic"""
    strategy = AggressiveScalperStrategy('ETH-USD')
    strategy.signal_cooldown_seconds = 60
    
    market_data = {
        'mark_price': 3000.0,
        'indicators': {'price_change_5m': 0.05, 'rsi': 60}
    }
    account_state = {'total_raw_usd': 20.0}
    
    # First signal
    signal1 = await strategy.generate_signal(market_data, account_state)
    assert signal1 is not None
    
    # Immediate second signal (should be blocked)
    signal2 = await strategy.generate_signal(market_data, account_state)
    assert signal2 is None
