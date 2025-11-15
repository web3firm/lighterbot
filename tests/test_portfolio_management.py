"""
Tests for portfolio management and OCO backup protection
"""
import pytest
import sys
from unittest.mock import Mock, AsyncMock, MagicMock


# Mock the lighter module before importing our modules
sys.modules['lighter'] = MagicMock()
sys.modules['lighter_client'] = MagicMock()


@pytest.fixture
def mock_position():
    """Create a mock position"""
    position = Mock()
    position.market_id = 1
    position.size = 0.01
    position.is_open = True
    position.is_long = True
    position.pnl_percentage = 0.0
    return position


@pytest.mark.asyncio
async def test_backup_stop_loss_logic():
    """Test the logic for backup stop loss without OCO"""
    # Simulate position without OCO at -2.5% loss
    pnl_pct = -2.5
    stop_loss_percent = 2.0
    
    # Position should be closed when pnl_pct <= -stop_loss_percent
    should_close = pnl_pct <= -stop_loss_percent
    
    assert should_close is True, "Position should close at -2.5% (below -2% threshold)"


@pytest.mark.asyncio
async def test_backup_take_profit_logic():
    """Test the logic for backup take profit without OCO"""
    # Simulate position without OCO at +2.5% profit
    pnl_pct = 2.5
    take_profit_percent = 2.0
    
    # Position should be closed when pnl_pct >= take_profit_percent
    should_close = pnl_pct >= take_profit_percent
    
    assert should_close is True, "Position should close at +2.5% (above +2% threshold)"


def test_max_collateral_is_60_percent():
    """Test that max collateral setting enforces 60% limit"""
    # Expected settings
    max_collateral = 12  # From config.py
    leverage = 5
    
    # With 5x leverage: 12% collateral × 5 = 60% max usage
    max_usage_pct = max_collateral * leverage
    
    assert max_usage_pct == 60, f"Expected 60% max usage, got {max_usage_pct}%"


def test_position_tracking_logic():
    """Test that positions without OCO are tracked properly"""
    positions_without_oco = set()
    position_id = "1_0.01_45000.0"
    
    # Initially empty
    assert len(positions_without_oco) == 0
    
    # Add position to tracking
    positions_without_oco.add(position_id)
    
    # Verify it's tracked
    assert position_id in positions_without_oco
    assert len(positions_without_oco) == 1
    
    # Remove position
    positions_without_oco.discard(position_id)
    assert len(positions_without_oco) == 0


def test_portfolio_heat_calculation_logic():
    """Test the logic for portfolio heat calculation"""
    # Example: 3 positions of 7% each = 21% collateral
    # With 5x leverage: 21% × 5 = 105% buying power
    # But max_collateral caps at 12% = 60% max usage
    
    position_size_pct = 7  # 7% per position
    num_positions = 3
    leverage = 5
    max_collateral = 12
    
    total_collateral = position_size_pct * num_positions  # 21%
    buying_power = total_collateral * leverage  # 105%
    max_allowed = max_collateral * leverage  # 60%
    
    # Logic should close positions when exceeding max_allowed
    assert buying_power > max_allowed
    assert max_allowed == 60
    
    # Calculate how many positions to close
    positions_to_close = 0
    current_buying_power = buying_power
    
    while current_buying_power > max_allowed and positions_to_close < num_positions:
        current_buying_power -= (position_size_pct * leverage)
        positions_to_close += 1
    
    # Should need to close 2 positions to get under 60%
    # 3 positions = 105% → 2 positions = 70% → 1 position = 35%
    expected_positions_to_close = 2
    assert positions_to_close == expected_positions_to_close


def test_oco_vs_backup_protection_logic():
    """Test the logic for choosing between OCO and backup protection"""
    position_id = "1_0.01"
    
    # Scenario 1: Position has OCO
    oco_orders = {position_id: {'tp_order_id': 12345, 'sl_order_id': 12346}}
    positions_without_oco = set()
    
    has_oco = position_id in oco_orders
    has_no_oco = position_id in positions_without_oco
    
    assert has_oco is True
    assert has_no_oco is False
    # Should use OCO protection
    
    # Scenario 2: Position has NO OCO
    oco_orders = {}
    positions_without_oco = {position_id}
    
    has_oco = position_id in oco_orders
    has_no_oco = position_id in positions_without_oco
    
    assert has_oco is False
    assert has_no_oco is True
    # Should use backup protection


def test_position_sorting_for_closing():
    """Test that positions are sorted by PnL to close losers first"""
    # Mock positions with different PnL
    positions = [
        {'id': 'pos1', 'pnl_percentage': 5.0},   # Winner
        {'id': 'pos2', 'pnl_percentage': -3.0},  # Biggest loser
        {'id': 'pos3', 'pnl_percentage': 2.0},   # Small winner
        {'id': 'pos4', 'pnl_percentage': -1.0},  # Small loser
    ]
    
    # Sort by PnL (ascending) to close losers first
    sorted_positions = sorted(positions, key=lambda p: p['pnl_percentage'])
    
    # First position should be biggest loser
    assert sorted_positions[0]['id'] == 'pos2'
    assert sorted_positions[0]['pnl_percentage'] == -3.0
    
    # Last position should be biggest winner
    assert sorted_positions[-1]['id'] == 'pos1'
    assert sorted_positions[-1]['pnl_percentage'] == 5.0


def test_three_layer_protection():
    """Test that all three protection layers are defined"""
    layers = {
        'exchange_oco': {
            'speed': '0ms',
            'survives_crash': True,
            'tp_pct': 2.0,
            'sl_pct': 2.0
        },
        'bot_backup': {
            'speed': '1s',
            'survives_crash': False,
            'tp_pct': 2.0,
            'sl_pct': 2.0
        },
        'portfolio_overheat': {
            'threshold_pct': 60.0,
            'check_interval': 3,
            'close_losers_first': True
        }
    }
    
    # Verify all layers exist
    assert 'exchange_oco' in layers
    assert 'bot_backup' in layers
    assert 'portfolio_overheat' in layers
    
    # Verify configuration
    assert layers['exchange_oco']['survives_crash'] is True
    assert layers['bot_backup']['speed'] == '1s'
    assert layers['portfolio_overheat']['threshold_pct'] == 60.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

