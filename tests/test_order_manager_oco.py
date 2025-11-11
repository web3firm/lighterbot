import pytest
import asyncio
from order_manager import OrderManager
from utils import market_metadata

@pytest.mark.asyncio
async def test_place_oco_dry_run(monkeypatch):
    # Force dry_run mode
    import config
    original = config.settings.dry_run
    config.settings.dry_run = True

    om = OrderManager()
    await market_metadata.set_market(1, "BTC-PERP", 6, 6, 2)

    # Monkeypatch client create_oco_orders to ensure no network call
    async def fake_create_oco_orders(**kwargs):
        return ({}, "tx_hash_dummy", None)

    from lighter_client import get_client
    client = await get_client()
    client.create_oco_orders = fake_create_oco_orders  # type: ignore

    ok = await om.place_oco("buy", 0.001, tp_price=50000.0, sl_price=48000.0, sl_trigger=48200.0)
    assert ok is True

    config.settings.dry_run = original
