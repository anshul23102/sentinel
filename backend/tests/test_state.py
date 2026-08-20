import pytest
import state


@pytest.mark.asyncio
async def test_window_is_time_based_not_sample_count_based(sid):
    """Regression test for a real bug found while merging upstream PR #76
    (independently confirmed here): a count-capped window means '60 seconds'
    only holds true at exactly ~1 req/s. At this system's actual traffic
    weights, a busy endpoint's 60-sample window covered as little as ~8
    real seconds and a quiet endpoint's covered ~100 — a 12x disparity in
    what 'recent history' meant per endpoint. Fixed by switching to a
    wall-clock-bounded window (a Redis sorted set), verified here with an
    explicit fake clock rather than relying on real elapsed time."""
    key = state.latency_key(sid, "/api/test")
    base = 1_000_000.0

    # Simulate a busy endpoint: 100 requests within the same 5-second span
    # (well inside the 60s window) — a count cap would have evicted the
    # first 40 of these; a time-based window must keep all of them.
    for i in range(100):
        await state.push_window(sid, key, float(i), "/api/test", now=base + i * 0.05)
    window = await state.get_window(key, now=base + 5.0)
    assert len(window) == 100  # nothing evicted — all within WINDOW_SECONDS

    # Now push one more sample well past 60s after the LAST burst entry
    # (base + 4.95) — everything from the burst should be evicted as stale,
    # regardless of how many samples they were.
    later = base + 4.95 + 65.0
    await state.push_window(sid, key, 999.0, "/api/test", now=later)
    window = await state.get_window(key, now=later)
    assert window == [999.0]


@pytest.mark.asyncio
async def test_known_endpoints_tracked_per_session(sid):
    await state.push_window(sid, state.latency_key(sid, "/api/a"), 1.0, "/api/a")
    await state.push_window(sid, state.latency_key(sid, "/api/b"), 1.0, "/api/b")
    endpoints = await state.get_known_endpoints(sid)
    assert set(endpoints) == {"/api/a", "/api/b"}


@pytest.mark.asyncio
async def test_known_endpoints_isolated_between_sessions(sid):
    other = sid + "-other"
    await state.push_window(sid, state.latency_key(sid, "/api/a"), 1.0, "/api/a")
    assert await state.get_known_endpoints(other) == []


@pytest.mark.asyncio
async def test_active_anomaly_lifecycle(sid):
    assert await state.get_active_anomaly(sid, "test_key") is None
    await state.set_active_anomaly(sid, "test_key", {"severity": "critical"})
    got = await state.get_active_anomaly(sid, "test_key")
    assert got == {"severity": "critical"}
    await state.clear_active_anomaly(sid, "test_key")
    assert await state.get_active_anomaly(sid, "test_key") is None


@pytest.mark.asyncio
async def test_scenario_round_trip(sid):
    default = await state.get_scenario(sid)
    assert default["current"] == "normal"  # honest default before anything is set

    await state.set_scenario(sid, "db_slowdown", 1.5, 1234.5)
    got = await state.get_scenario(sid)
    assert got == {"current": "db_slowdown", "intensity": 1.5, "start_time": 1234.5}


@pytest.mark.asyncio
async def test_scenario_isolated_between_sessions(sid):
    other = sid + "-other"
    await state.set_scenario(sid, "memory_leak", 1.0, 0.0)
    other_scenario = await state.get_scenario(other)
    assert other_scenario["current"] == "normal"  # unaffected by sid's change
