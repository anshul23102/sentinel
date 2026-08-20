import uuid
import pytest
from fastapi import HTTPException
import ratelimit


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, ip="1.2.3.4", headers=None):
        self.client = _FakeClient(ip)
        self.headers = headers or {}


def _unique_bucket() -> str:
    return f"testbucket-{uuid.uuid4()}"


@pytest.mark.asyncio
async def test_allows_requests_under_the_limit():
    dep = ratelimit.rate_limit(_unique_bucket(), limit=3, window_seconds=60)
    req = _FakeRequest()
    for _ in range(3):
        await dep(req)  # must not raise


@pytest.mark.asyncio
async def test_blocks_requests_over_the_limit_with_429():
    dep = ratelimit.rate_limit(_unique_bucket(), limit=3, window_seconds=60)
    req = _FakeRequest()
    for _ in range(3):
        await dep(req)
    with pytest.raises(HTTPException) as exc_info:
        await dep(req)
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_different_ips_have_independent_limits():
    dep = ratelimit.rate_limit(_unique_bucket(), limit=2, window_seconds=60)
    req_a = _FakeRequest(ip="1.1.1.1")
    req_b = _FakeRequest(ip="2.2.2.2")
    await dep(req_a); await dep(req_a)  # exhaust A's limit
    await dep(req_b)  # B is unaffected
    with pytest.raises(HTTPException):
        await dep(req_a)


@pytest.mark.asyncio
async def test_admin_key_bypasses_the_limit(monkeypatch):
    monkeypatch.setattr(ratelimit, "ADMIN_API_KEY", "secret-test-key")
    dep = ratelimit.rate_limit(_unique_bucket(), limit=1, window_seconds=60)
    req = _FakeRequest(headers={"x-api-key": "secret-test-key"})
    for _ in range(5):
        await dep(req)  # must never raise, regardless of limit


@pytest.mark.asyncio
async def test_wrong_api_key_does_not_bypass(monkeypatch):
    monkeypatch.setattr(ratelimit, "ADMIN_API_KEY", "secret-test-key")
    dep = ratelimit.rate_limit(_unique_bucket(), limit=1, window_seconds=60)
    req = _FakeRequest(headers={"x-api-key": "wrong-key"})
    await dep(req)
    with pytest.raises(HTTPException):
        await dep(req)


@pytest.mark.asyncio
async def test_respects_x_forwarded_for():
    dep = ratelimit.rate_limit(_unique_bucket(), limit=1, window_seconds=60)
    req = _FakeRequest(ip="10.0.0.1", headers={"x-forwarded-for": "203.0.113.5, 10.0.0.1"})
    await dep(req)
    with pytest.raises(HTTPException):
        # same forwarded client should be limited even though req.client.host differs
        await dep(_FakeRequest(ip="10.0.0.1", headers={"x-forwarded-for": "203.0.113.5, 10.0.0.1"}))
