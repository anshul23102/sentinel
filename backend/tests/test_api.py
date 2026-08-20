"""API-level tests against the real FastAPI app (in-process, via ASGI
transport — no network, no separate server process). GROQ_API_KEY is forced
empty by conftest.py, so these never make a real external API call; the
'AI unavailable' degradation path is itself part of what's being tested."""
import uuid
import pytest
import httpx

import main


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _sid_header(sid: str) -> dict:
    # X-Forwarded-For gives each test its own rate-limit bucket — otherwise
    # every test shares httpx's one synthetic client IP under ASGI transport,
    # and tests hitting rate-limited endpoints would silently contaminate
    # each other's counters through the same Redis key.
    return {"X-Session-Id": sid, "X-Forwarded-For": sid}


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(client, sid):
    r = await client.get("/api/health", headers=_sid_header(sid))
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


@pytest.mark.asyncio
async def test_scenario_default_is_normal(client, sid):
    r = await client.get("/api/scenario", headers=_sid_header(sid))
    assert r.status_code == 200
    assert r.json()["current"] == "normal"


@pytest.mark.asyncio
async def test_scenario_rejects_unknown_scenario(client, sid):
    r = await client.post("/api/scenario", headers=_sid_header(sid),
                           json={"scenario": "not_a_real_scenario", "intensity": 1.0})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_two_sessions_have_independent_scenarios(client):
    sid_a = f"test-{uuid.uuid4()}"
    sid_b = f"test-{uuid.uuid4()}"
    try:
        await client.post("/api/scenario", headers=_sid_header(sid_a),  # unique X-Forwarded-For too
                           json={"scenario": "db_slowdown", "intensity": 1.0})
        await client.post("/api/scenario", headers=_sid_header(sid_b),
                           json={"scenario": "memory_leak", "intensity": 1.0})

        r_a = await client.get("/api/scenario", headers=_sid_header(sid_a))
        r_b = await client.get("/api/scenario", headers=_sid_header(sid_b))

        assert r_a.json()["current"] == "db_slowdown"
        assert r_b.json()["current"] == "memory_leak"  # NOT affected by A's change
    finally:
        import db
        await db.delete_session_data(sid_a)
        await db.delete_session_data(sid_b)


@pytest.mark.asyncio
async def test_chat_rejects_overlong_message(client, sid):
    r = await client.post("/api/chat", headers=_sid_header(sid),
                           json={"message": "x" * 5000, "history": []})
    assert r.status_code == 422  # Pydantic max_length rejection


@pytest.mark.asyncio
async def test_chat_degrades_gracefully_without_api_key(client, sid):
    r = await client.post("/api/chat", headers=_sid_header(sid),
                           json={"message": "What is the system health?", "history": []})
    assert r.status_code == 200
    assert "unavailable" in r.json()["response"].lower()


@pytest.mark.asyncio
async def test_scenario_rate_limit_returns_429_after_limit(client, sid):
    for _ in range(20):
        r = await client.post("/api/scenario", headers=_sid_header(sid),
                               json={"scenario": "normal", "intensity": 1.0})
        assert r.status_code == 200
    r = await client.post("/api/scenario", headers=_sid_header(sid),
                           json={"scenario": "normal", "intensity": 1.0})
    assert r.status_code == 429
    assert "Retry-After" in r.headers


@pytest.mark.asyncio
async def test_incident_report_handles_no_anomalies(client, sid):
    r = await client.post("/api/incident-report", headers=_sid_header(sid))
    assert r.status_code == 200
    assert "report" in r.json()
