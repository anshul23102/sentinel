"""Coverage for the session-identity hardening: X-Session-Id format
validation, the per-IP rate limit on *creating* new sessions, and the
process-wide MAX_SESSIONS cap. See main.py's "Session identity" section and
session_manager.py's CapacityExceeded for the behavior under test.

Every test that successfully creates a real session (a 200, not a 400/429/503)
spins up two live background tasks (log_pipeline + periodic_scan) that would
otherwise keep running — and holding a Postgres connection out of the pool's
fixed 10 — for the rest of the whole test suite. `_new_sids` tracks every sid
a test actually created and tears its background tasks down afterward, the
same way session_manager's own idle reaper would, just immediately instead
of after 5 minutes.
"""
import uuid
import pytest
import httpx

import main
import session_manager


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def _new_sids():
    created: list[str] = []
    yield created
    for sid in created:
        await main._cleanup_session(sid)
        session_manager._sessions.pop(sid, None)


@pytest.mark.asyncio
async def test_invalid_session_id_is_rejected(client):
    r = await client.get("/api/health", headers={
        "X-Session-Id": "not valid! / has spaces",
        "X-Forwarded-For": f"invalid-sid-{uuid.uuid4()}",
    })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_overlong_session_id_is_rejected(client):
    r = await client.get("/api/health", headers={
        "X-Session-Id": "a" * 500,
        "X-Forwarded-For": f"overlong-sid-{uuid.uuid4()}",
    })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_new_session_creation_is_rate_limited_per_ip(client, _new_sids):
    ip = f"new-session-rl-{uuid.uuid4()}"
    # _new_session_rate_limit in main.py allows 10 new sessions per 60s per IP.
    for i in range(10):
        sid = f"{ip}-{i}"
        r = await client.get("/api/health", headers={"X-Session-Id": sid, "X-Forwarded-For": ip})
        assert r.status_code == 200
        _new_sids.append(sid)
    r = await client.get("/api/health", headers={
        "X-Session-Id": f"{ip}-overflow", "X-Forwarded-For": ip,
    })
    assert r.status_code == 429  # never created — nothing to add to _new_sids


@pytest.mark.asyncio
async def test_returning_session_is_not_throttled_by_the_new_session_guard(client, _new_sids):
    ip = f"returning-rl-{uuid.uuid4()}"
    sid = f"{ip}-sid"
    r = await client.get("/api/health", headers={"X-Session-Id": sid, "X-Forwarded-For": ip})
    assert r.status_code == 200
    _new_sids.append(sid)
    # Many repeat calls with the SAME sid must never trip the *new*-session
    # limiter, which only counts sessions that didn't exist yet.
    for _ in range(15):
        r = await client.get("/api/health", headers={"X-Session-Id": sid, "X-Forwarded-For": ip})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_session_capacity_cap_returns_503_once_full(client, monkeypatch, _new_sids):
    # Cap it to exactly one more than whatever's already running, so this
    # test is robust to how many sessions earlier tests created.
    monkeypatch.setattr(session_manager, "MAX_SESSIONS", session_manager.active_session_count() + 1)

    ip_a = f"capacity-{uuid.uuid4()}"
    sid_a = f"{ip_a}-sid"
    r1 = await client.get("/api/health", headers={"X-Session-Id": sid_a, "X-Forwarded-For": ip_a})
    assert r1.status_code == 200
    _new_sids.append(sid_a)

    ip_b = f"capacity-{uuid.uuid4()}"
    r2 = await client.get("/api/health", headers={"X-Session-Id": f"{ip_b}-sid", "X-Forwarded-For": ip_b})
    assert r2.status_code == 503  # refused — nothing created, nothing to add
