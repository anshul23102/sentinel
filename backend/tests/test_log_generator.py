import asyncio
import time
from unittest.mock import AsyncMock, patch
import pytest

import log_generator


@pytest.mark.asyncio
async def test_run_generator_cadence_maintained_despite_db_latency():
    """Verify that run_generator decouples sleep timer from database insertion
    latency using time.monotonic(), maintaining a strict 1-second cadence.
    """
    sid = "test-log-gen-cadence"
    timestamps = []

    async def fake_broadcast(msg):
        timestamps.append(time.monotonic())

    # Simulate 150ms database insertion latency
    async def fake_insert(s, b):
        await asyncio.sleep(0.15)

    scenario_mock = AsyncMock(
        return_value={"current": "normal", "intensity": 1.0, "start_time": time.time()}
    )

    with patch("log_generator.bulk_insert_logs", side_effect=fake_insert), \
         patch("log_generator.state.get_scenario", scenario_mock):
        task = asyncio.create_task(log_generator.run_generator(sid, fake_broadcast, rps=20))
        # Wait long enough for 2 ticks (approx 2.05s)
        await asyncio.sleep(2.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert len(timestamps) >= 2, f"Expected at least 2 broadcast ticks, got {len(timestamps)}"
    interval = timestamps[1] - timestamps[0]
    # Cadence should be ~1.0s (not 1.15s+ due to compounding DB latency)
    assert 0.95 <= interval <= 1.08, f"Clock drift observed: {interval:.3f}s"


@pytest.mark.asyncio
async def test_run_generator_zero_rps_no_traffic():
    """rps=0 should broadcast empty batches and sleep without touching Redis or DB."""
    sid = "test-log-gen-zero"
    received = []

    async def fake_broadcast(msg):
        received.append(msg)

    insert_mock = AsyncMock()
    scenario_mock = AsyncMock()

    with patch("log_generator.bulk_insert_logs", insert_mock), \
         patch("log_generator.state.get_scenario", scenario_mock):
        task = asyncio.create_task(log_generator.run_generator(sid, fake_broadcast, rps=0))
        await asyncio.sleep(1.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert len(received) >= 1
    assert received[0] == {"type": "logs", "data": []}
    insert_mock.assert_not_called()
    scenario_mock.assert_not_called()


@pytest.mark.asyncio
async def test_run_generator_realigns_after_db_latency_spike():
    """When a single DB insert takes longer than the 1s cadence window,
    sleep_duration drops to 0 and the loop resynchronizes without cascading backlog.
    """
    sid = "test-log-gen-spike"
    timestamps = []

    async def fake_broadcast(msg):
        timestamps.append(time.monotonic())

    delays = [1.2, 0.1]

    async def fake_insert(s, b):
        delay = delays.pop(0) if delays else 0.1
        await asyncio.sleep(delay)

    scenario_mock = AsyncMock(
        return_value={"current": "normal", "intensity": 1.0, "start_time": time.time()}
    )

    with patch("log_generator.bulk_insert_logs", side_effect=fake_insert), \
         patch("log_generator.state.get_scenario", scenario_mock):
        task = asyncio.create_task(log_generator.run_generator(sid, fake_broadcast, rps=10))
        await asyncio.sleep(2.6)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert len(timestamps) >= 2


@pytest.mark.asyncio
async def test_run_generator_cancels_cleanly():
    """Verify run_generator cancels cleanly upon receiving CancelledError."""
    sid = "test-log-gen-cancel"
    broadcast_mock = AsyncMock()
    insert_mock = AsyncMock()
    scenario_mock = AsyncMock(
        return_value={"current": "normal", "intensity": 1.0, "start_time": time.time()}
    )

    with patch("log_generator.bulk_insert_logs", insert_mock), \
         patch("log_generator.state.get_scenario", scenario_mock):
        task = asyncio.create_task(log_generator.run_generator(sid, broadcast_mock, rps=10))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert task.cancelled()
