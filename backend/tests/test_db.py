import pytest
import db


def _log(endpoint="/api/test", status=200, latency=72.0, ts="2026-01-01T00:00:00"):
    return {
        "timestamp": ts, "endpoint": endpoint, "method": "GET",
        "status_code": status, "latency_ms": latency,
        "error_message": None, "service": "test-service", "user_id": "u1",
        "metadata": {},
    }


@pytest.mark.asyncio
async def test_logs_are_scoped_by_session(sid):
    other = sid + "-other"
    await db.bulk_insert_logs(sid, [_log()])
    await db.bulk_insert_logs(other, [_log(), _log()])

    assert len(await db.get_recent_logs(sid, limit=100)) == 1
    assert len(await db.get_recent_logs(other, limit=100)) == 2

    await db.delete_session_data(other)


@pytest.mark.asyncio
async def test_anomalies_are_scoped_by_session(sid):
    other = sid + "-other"
    anomaly = {
        "detected_at": "2026-01-01T00:00:00", "anomaly_type": "latency_spike",
        "severity": "warning", "endpoint": "/api/test", "description": "test",
        "root_cause_chain": [], "suggested_fix": "",
    }
    await db.insert_anomaly(sid, anomaly)
    assert len(await db.get_recent_anomalies(sid, limit=10)) == 1
    assert len(await db.get_recent_anomalies(other, limit=10)) == 0


@pytest.mark.asyncio
async def test_endpoint_stats_aggregate_correctly(sid):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    await db.bulk_insert_logs(sid, [
        _log(status=200, latency=100.0, ts=now),
        _log(status=200, latency=200.0, ts=now),
        _log(status=500, latency=300.0, ts=now),
    ])
    stats = await db.get_endpoint_stats(sid, minutes=5)
    assert len(stats) == 1
    s = stats[0]
    assert s["total_requests"] == 3
    assert s["error_5xx"] == 1
    assert s["avg_latency"] == pytest.approx(200.0)


@pytest.mark.asyncio
async def test_prune_old_logs_only_affects_the_given_session(sid):
    other = sid + "-other"
    old_ts = "2020-01-01T00:00:00"
    await db.bulk_insert_logs(sid, [_log(ts=old_ts)])
    await db.bulk_insert_logs(other, [_log(ts=old_ts)])

    await db.prune_old_logs(sid, minutes=15)

    assert await db.get_recent_logs(sid, limit=10) == []
    assert len(await db.get_recent_logs(other, limit=10)) == 1  # untouched
    await db.delete_session_data(other)


@pytest.mark.asyncio
async def test_seasonal_bucket_upsert_and_read(sid):
    await db.upsert_seasonal_bucket(sid, "/api/test", 1, 100.0, 0.01, 30.0)
    await db.upsert_seasonal_bucket(sid, "/api/test", 1, 150.0, 0.02, 25.0)  # same bucket, should overwrite
    history = await db.get_seasonal_history(sid, "/api/test", limit=10)
    assert history == [150.0]


@pytest.mark.asyncio
async def test_delete_session_data_removes_everything(sid):
    await db.bulk_insert_logs(sid, [_log()])
    anomaly = {
        "detected_at": "2026-01-01T00:00:00", "anomaly_type": "latency_spike",
        "severity": "warning", "endpoint": "/api/test", "description": "test",
        "root_cause_chain": [], "suggested_fix": "",
    }
    await db.insert_anomaly(sid, anomaly)
    await db.upsert_seasonal_bucket(sid, "/api/test", 1, 100.0, 0.01, 30.0)

    await db.delete_session_data(sid)

    assert await db.get_recent_logs(sid, limit=10) == []
    assert await db.get_recent_anomalies(sid, limit=10) == []
    assert await db.get_seasonal_history(sid, "/api/test", limit=10) == []
