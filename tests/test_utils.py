import asyncio
import os
import pytest

from utils import market_metadata, resolve_market_metadata, OrderIndexer, retry_async

class DummyClient:
    pass

@pytest.mark.asyncio
async def test_market_metadata_resolution():
    client = DummyClient()
    mid = await resolve_market_metadata(client, "BTC-PERP")
    assert mid == 1
    assert market_metadata.get_market(mid)["symbol"] == "BTC-PERP"

@pytest.mark.asyncio
async def test_order_indexer_persistence(tmp_path):
    fp = tmp_path / "order_index.json"
    indexer = OrderIndexer(str(fp))
    first = await indexer.get_next()
    second = await indexer.get_next()
    assert second == first + 1
    # Reload
    indexer2 = OrderIndexer(str(fp))
    peek = await indexer2.peek()
    assert peek == second

@pytest.mark.asyncio
async def test_retry_async_success_after_failures():
    attempts = {"count": 0}

    @retry_async(max_attempts=4, initial_delay=0.01, max_delay=0.05, jitter=False)
    async def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary")
        return "ok"

    result = await flaky()
    assert result == "ok"
    assert attempts["count"] == 3

@pytest.mark.asyncio
async def test_retry_async_exhaust():
    @retry_async(max_attempts=2, initial_delay=0.01, max_delay=0.02, jitter=False)
    async def always_fail():
        raise ValueError("bad")

    with pytest.raises(ValueError):
        await always_fail()
