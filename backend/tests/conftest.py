"""Points every test at isolated infra — a separate Postgres database
(sentinel_test) and a separate Redis logical DB (index 1, vs the app's
default 0) — so running the suite never touches live demo data. These env
vars must be set before db.py / state.py are imported anywhere, since both
read them at import time.

Uses setdefault rather than a hard assignment so CI (or any environment
whose Postgres/Redis need different credentials or a different host) can
export DATABASE_URL / REDIS_URL before pytest runs and have that take
precedence over the local-dev default below.
"""
import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql://localhost/sentinel_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("GROQ_API_KEY", "")  # tests must not require a real key
# The test client is a single fake "connection" for every test, so without
# this, all tests would share one rate-limit bucket per real client IP.
# Tests deliberately set X-Forwarded-For to their own sid to get an
# independent bucket per test — safe here since the test process is the
# only thing ever calling itself, but ratelimit.py defaults this off in
# production because trusting a client-supplied header unconditionally
# lets any real caller bypass rate limiting by sending a fresh fake IP.
os.environ.setdefault("TRUST_PROXY_HEADERS", "true")

import pytest
import pytest_asyncio

import db
import state


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _init_test_db():
    await db.init_db()
    yield


@pytest.fixture
def sid() -> str:
    """A fresh, unique session id per test — tests never share state."""
    return f"test-{uuid.uuid4()}"


@pytest_asyncio.fixture(autouse=True)
async def _cleanup(sid):
    """Runs after every test: drop this test's rows/keys so the test DB and
    test Redis DB don't grow across a full suite run."""
    yield
    try:
        await db.delete_session_data(sid)
    except Exception:
        pass
    c = state.get_client()
    keys = await c.keys(f"sentinel:{sid}:*")
    if keys:
        await c.delete(*keys)
