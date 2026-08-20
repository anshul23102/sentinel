import pytest
import state


@pytest.mark.asyncio
async def test_window_caps_at_maxlen(sid):
    key = state.latency_key(sid, "/api/test")
    for i in range(state.WINDOW_MAXLEN + 20):
        await state.push_window(sid, key, float(i), "/api/test")
    window = await state.get_window(key)
    assert len(window) == state.WINDOW_MAXLEN
    assert window[-1] == float(state.WINDOW_MAXLEN + 19)  # newest value kept
    assert window[0] == float(20)  # oldest values trimmed off


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
