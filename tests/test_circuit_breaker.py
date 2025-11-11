import asyncio
import pytest
from utils import CircuitBreaker, circuit_breaker

@pytest.mark.asyncio
async def test_circuit_breaker_opens():
    breaker = CircuitBreaker(failure_threshold=3, reset_timeout=0.5, half_open_max_calls=1)
    calls = {"n": 0}

    @circuit_breaker(breaker)
    async def failing():
        calls["n"] += 1
        raise RuntimeError("fail")

    # Trip breaker
    for _ in range(3):
        with pytest.raises(RuntimeError):
            await failing()
    # Should now be open
    with pytest.raises(RuntimeError) as ei:
        await failing()
    assert "Circuit breaker is open" in str(ei.value)

    # Wait for half-open window
    await asyncio.sleep(0.6)

    @circuit_breaker(breaker)
    async def succeeding():
        return "ok"

    # First half-open call should pass (and close breaker)
    assert await succeeding() == "ok"

    # After success, breaker closed; failing again increments normally
    with pytest.raises(RuntimeError):
        await failing()
