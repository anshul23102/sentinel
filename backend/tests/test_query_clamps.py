"""
Regression test for issue #69 — limit/minutes query params were passed straight
into SQL with no clamp. A negative LIMIT is "unlimited" in SQLite (dumps the whole
table); a negative `minutes` builds an invalid "--N minutes" modifier so strftime
returns NULL and the endpoint silently returns [].

Driven with asyncio.run() against a temp DB (no pytest-asyncio needed).
"""

import asyncio
from datetime import datetime, timezone

import db


def _seed(tmp_path, monkeypatch, n=5):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test_logs.db"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    logs = [
        {
            "timestamp": now,
            "endpoint": "/api/products",
            "method": "GET",
            "status_code": 200,
            "latency_ms": 80.0,
            "service": "web",
        }
        for _ in range(n)
    ]

    async def _run():
        await db.init_db()
        await db.bulk_insert_logs(logs)

    asyncio.run(_run())


def test_negative_limit_is_clamped_not_unlimited(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, n=5)
    # Before the fix: LIMIT -1 -> SQLite returns ALL 5 rows (unbounded).
    # After the fix: clamped to 1.
    rows = asyncio.run(db.get_recent_logs(limit=-1))
    assert len(rows) == 1


def test_huge_limit_is_capped(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, n=5)
    rows = asyncio.run(db.get_recent_logs(limit=10_000_000))
    # Capped at MAX_ROW_LIMIT; with only 5 rows we just get the 5 back, never a crash.
    assert len(rows) == 5
    assert db.MAX_ROW_LIMIT == 1000


def test_negative_anomaly_limit_is_clamped(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, n=0)
    # No anomalies seeded, but the point is it must not raise / dump — returns [].
    rows = asyncio.run(db.get_recent_anomalies(limit=-1))
    assert rows == []


def test_negative_minutes_still_returns_data(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, n=5)
    # Before the fix: minutes=-5 -> "--5 minutes" -> strftime NULL -> [] (silent no-data).
    # After the fix: clamped to 1 -> the just-inserted rows are within the window.
    stats = asyncio.run(db.get_endpoint_stats(minutes=-5))
    assert stats, "negative minutes should be clamped, not silently return empty"
    assert stats[0]["endpoint"] == "/api/products"
    assert stats[0]["total_requests"] == 5


def test_timeseries_negative_minutes_clamped(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, n=3)
    series = asyncio.run(db.get_timeseries(minutes=-10))
    assert series, "negative minutes should be clamped for timeseries too"
