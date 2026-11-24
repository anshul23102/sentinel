"""POST /api/ingest: the path that lets a real service feed Sentinel its own
request telemetry instead of the built-in simulator. Tests run against the
real FastAPI app, real Postgres and real Redis (see conftest.py)."""
import asyncio
import json
import time
import uuid

import httpx
import pytest

import db
import main
import ratelimit
import session_manager
import state


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def live_sid():
    """A fresh live-* session id, torn down completely afterwards (background
    tasks, Postgres rows, Redis keys) so nothing leaks into other tests."""
    sid = f"live-{uuid.uuid4()}"
    yield sid
    await main._cleanup_session(sid)
    session_manager._sessions.pop(sid, None)
    c = state.get_client()
    keys = await c.keys(f"sentinel:{sid}:*")
    if keys:
        await c.delete(*keys)


def _headers(sid: str) -> dict:
    # X-Forwarded-For gives each test its own rate-limit bucket (see conftest).
    return {"X-Session-Id": sid, "X-Forwarded-For": sid}


def _log(endpoint="/api/orders", status=200, latency=70.0, **extra):
    return {"endpoint": endpoint, "status_code": status, "latency_ms": latency, **extra}


@pytest.mark.asyncio
async def test_valid_batch_is_accepted_and_persisted(client, live_sid):
    body = {"logs": [_log(latency=70.0 + i) for i in range(10)]}
    r = await client.post("/api/ingest", headers=_headers(live_sid), json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["accepted"] == 10 and data["session_id"] == live_sid
    rows = await db.get_recent_logs(live_sid, limit=50)
    assert len(rows) == 10
    assert all(row["endpoint"] == "/api/orders" for row in rows)
    assert all(row["metadata"] is not None and "ingest" in row["metadata"] for row in rows)


@pytest.mark.asyncio
async def test_client_supplied_timestamps_are_ignored(client, live_sid):
    # Letting a caller back-date records would let it write into the past of
    # the time-windowed baselines the detector depends on.
    body = {"logs": [{**_log(), "timestamp": "1999-01-01T00:00:00"}]}
    r = await client.post("/api/ingest", headers=_headers(live_sid), json=body)
    assert r.status_code == 200
    rows = await db.get_recent_logs(live_sid, limit=5)
    assert rows and not rows[0]["timestamp"].startswith("1999")


@pytest.mark.asyncio
async def test_live_sessions_never_run_the_traffic_simulator(client, live_sid):
    await client.post("/api/ingest", headers=_headers(live_sid), json={"logs": [_log()]})
    assert main.supervisor.get_task_status(f"periodic_scan:{live_sid}").get("running") is True
    assert "error" in main.supervisor.get_task_status(f"log_pipeline:{live_sid}")  # never registered


@pytest.mark.asyncio
async def test_non_live_sessions_still_get_the_simulator(client, sid):
    r = await client.get("/api/health", headers=_headers(sid))
    assert r.status_code == 200
    assert main.supervisor.get_task_status(f"log_pipeline:{sid}").get("running") is True


@pytest.mark.asyncio
async def test_ingested_error_burst_is_detected_end_to_end(client, live_sid):
    """The whole point of the endpoint: real telemetry in, a real anomaly out,
    through the same detector the simulator uses."""
    healthy = {"logs": [_log("/api/checkout", 200, 70.0 + (i % 5)) for i in range(30)]}
    for _ in range(3):
        assert (await client.post("/api/ingest", headers=_headers(live_sid), json=healthy)).status_code == 200

    burst = {"logs": [_log("/api/checkout", 503 if i < 9 else 200, 72.0) for i in range(30)]}
    detected = None
    for _ in range(4):
        r = await client.post("/api/ingest", headers=_headers(live_sid), json=burst)
        detected = next((a for a in r.json()["anomalies"] if a["type"] == "error_surge"), None)
        if detected:
            break
    assert detected is not None and detected["endpoint"] == "/api/checkout"

    persisted = await client.get("/api/anomalies", headers=_headers(live_sid))
    assert any(a["anomaly_type"] == "error_surge" for a in persisted.json())
    health = (await client.get("/api/health", headers=_headers(live_sid))).json()
    assert health["/api/checkout"]["error_rate"] > 0.15


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_log", [
    _log(status=99), _log(status=600), _log(latency=-1.0), _log(latency=10_000_000.0),
    _log(endpoint="no-leading-slash"), _log(endpoint="/has space"), _log(endpoint="/" + "a" * 250),
    {**_log(), "method": "HACK"}, {"endpoint": "/api/x", "latency_ms": 5.0},  # missing status_code
])
async def test_invalid_records_are_rejected_with_422(client, live_sid, bad_log):
    r = await client.post("/api/ingest", headers=_headers(live_sid), json={"logs": [bad_log]})
    assert r.status_code == 422
    assert await db.get_recent_logs(live_sid, limit=5) == []  # nothing partially written


@pytest.mark.asyncio
async def test_empty_and_oversized_batches_are_rejected(client, live_sid):
    assert (await client.post("/api/ingest", headers=_headers(live_sid), json={"logs": []})).status_code == 422
    too_many = {"logs": [_log() for _ in range(main.MAX_INGEST_BATCH + 1)]}
    assert (await client.post("/api/ingest", headers=_headers(live_sid), json=too_many)).status_code == 422


@pytest.mark.asyncio
async def test_malformed_json_is_a_422_not_a_500(client, live_sid):
    r = await client.post("/api/ingest", headers={**_headers(live_sid), "Content-Type": "application/json"},
                          content=b"{not json")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_body_over_the_cap_is_rejected_by_content_length(client, live_sid):
    huge = json.dumps({"logs": [_log(error_message="x" * 400) for _ in range(500)], "pad": "y" * 300_000})
    r = await client.post("/api/ingest", headers={**_headers(live_sid), "Content-Type": "application/json"},
                          content=huge.encode())
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_chunked_body_over_the_cap_is_rejected_even_without_content_length(client, live_sid):
    async def chunks():
        for _ in range(40):
            yield b"x" * 10_000  # 400 KB total, no Content-Length header sent
    r = await client.post("/api/ingest", headers={**_headers(live_sid), "Content-Type": "application/json"},
                          content=chunks())
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_too_many_distinct_endpoints_in_one_request(client, live_sid):
    body = {"logs": [_log(f"/api/e{i}") for i in range(main.MAX_INGEST_ENDPOINTS_BATCH + 1)]}
    r = await client.post("/api/ingest", headers=_headers(live_sid), json=body)
    assert r.status_code == 422 and "route templates" in r.text


@pytest.mark.asyncio
async def test_per_session_endpoint_cap_stops_unbounded_state_growth(client, live_sid):
    # The classic mistake: sending raw URLs (/users/1, /users/2 ...) instead
    # of route templates would create unbounded per-endpoint Redis state.
    for start in range(0, main.MAX_ENDPOINTS_PER_SESSION, main.MAX_INGEST_ENDPOINTS_BATCH):
        body = {"logs": [_log(f"/api/e{start + i}") for i in range(main.MAX_INGEST_ENDPOINTS_BATCH)]}
        assert (await client.post("/api/ingest", headers=_headers(live_sid), json=body)).status_code == 200
    over = await client.post("/api/ingest", headers=_headers(live_sid), json={"logs": [_log("/api/one-too-many")]})
    assert over.status_code == 422
    # an endpoint already tracked is still fine
    again = await client.post("/api/ingest", headers=_headers(live_sid), json={"logs": [_log("/api/e0")]})
    assert again.status_code == 200


@pytest.mark.asyncio
async def test_scenario_injection_is_refused_for_live_sessions(client, live_sid):
    await client.post("/api/ingest", headers=_headers(live_sid), json={"logs": [_log()]})
    r = await client.post("/api/scenario", headers=_headers(live_sid), json={"scenario": "db_slowdown"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_api_key_is_enforced_when_lockdown_is_enabled(client, live_sid, monkeypatch):
    monkeypatch.setattr(ratelimit, "REQUIRE_API_KEY", True)
    monkeypatch.setattr(ratelimit, "ADMIN_API_KEY", "ingest-test-key")
    body = {"logs": [_log()]}
    assert (await client.post("/api/ingest", headers=_headers(live_sid), json=body)).status_code == 401
    ok = await client.post("/api/ingest", headers={**_headers(live_sid), "X-API-Key": "ingest-test-key"}, json=body)
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_ingest_is_rate_limited_per_ip(client, live_sid):
    # The limiter is a fixed-window counter keyed on int(time / 60). If this
    # burst straddled a minute boundary the counter would legitimately reset
    # mid-test (the documented 2x-burst-at-the-edge tradeoff of fixed
    # windows), so start the burst just after a window begins.
    seconds_into_window = time.time() % 60
    if seconds_into_window > 50:
        await asyncio.sleep(60 - seconds_into_window + 0.2)
    body = {"logs": [_log()]}
    statuses = [(await client.post("/api/ingest", headers=_headers(live_sid), json=body)).status_code for _ in range(61)]
    assert statuses[:60] == [200] * 60 and statuses[60] == 429
