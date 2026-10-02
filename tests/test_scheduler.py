"""Tests for RateScheduler."""

import asyncio
import time
import pytest
from app.engine.scheduler import RateScheduler


@pytest.mark.anyio
async def test_scheduler_tick_count_and_timing():
    """Verify scheduler generates approximately rate * duration ticks."""
    rate = 20.0  # 20 req/s -> 1 tick every 50ms
    duration = 0.5  # 0.5s -> approx 10 ticks
    scheduler = RateScheduler(rate=rate, duration=duration)

    ticks = []
    start = time.perf_counter()
    async for tick_time in scheduler.generate_ticks():
        ticks.append(tick_time)

    elapsed = time.perf_counter() - start
    assert 8 <= len(ticks) <= 12
    assert elapsed >= 0.45


@pytest.mark.anyio
async def test_scheduler_stop_early():
    """Verify scheduler stops immediately when stop() is called."""
    rate = 50.0
    duration = 2.0  # Would normally be 100 ticks
    scheduler = RateScheduler(rate=rate, duration=duration)

    ticks = []
    async for tick_time in scheduler.generate_ticks():
        ticks.append(tick_time)
        if len(ticks) == 5:
            scheduler.stop()

    assert len(ticks) == 5
