"""
Tests for database indexes (Issue #59).

Verifies that:
- Indexes are created during init_db()
- Repeated init_db() calls do not fail (idempotent)
- Existing databases continue working
- Index creation is idempotent
"""

import os
import sys
import pytest
import aiosqlite


def _get_isolated_db(tmp_path, test_id):
    """Create a fresh db module with DB_PATH pointing to a unique temp file."""
    # Use test function ID to ensure unique filename per test
    db_file = tmp_path / f"test_{test_id}.db"
    
    # Remove any cached db module to force fresh import
    for mod in list(sys.modules.keys()):
        if mod == "db" or mod.startswith("db."):
            del sys.modules[mod]
    
    # Set environment variable and import
    os.environ["DB_PATH"] = str(db_file)
    import db as db_module
    # Override the DB_PATH to ensure we're using our temp file
    db_module.DB_PATH = str(db_file)
    return db_module, db_file


@pytest.fixture
def isolated_db(tmp_path, request):
    """Provide a db module pointing to a temp file, cleaned up after test."""
    # Use request.node.name to get unique test function name
    db_module, db_file = _get_isolated_db(tmp_path, request.node.name)
    
    yield db_module
    
    # Cleanup after test
    try:
        # Close any open connections by forcing garbage collection
        import gc
        gc.collect()
        if db_file.exists():
            db_file.unlink()
        for ext in ["-wal", "-shm"]:
            wal_file = tmp_path / f"test_{request.node.name}{ext}"
            if wal_file.exists():
                wal_file.unlink()
    except Exception:
        pass


class TestIndexCreation:
    """Verify indexes are created during init_db()."""

    @pytest.mark.asyncio
    async def test_anomalies_detected_at_index_exists(self, isolated_db):
        await isolated_db.init_db()
        async with aiosqlite.connect(isolated_db.DB_PATH) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_anomalies_detected_at'"
            )
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_anomalies_endpoint_index_exists(self, isolated_db):
        await isolated_db.init_db()
        async with aiosqlite.connect(isolated_db.DB_PATH) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_anomalies_endpoint'"
            )
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_incidents_status_index_exists(self, isolated_db):
        await isolated_db.init_db()
        async with aiosqlite.connect(isolated_db.DB_PATH) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_incidents_status'"
            )
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_incidents_started_at_index_exists(self, isolated_db):
        await isolated_db.init_db()
        async with aiosqlite.connect(isolated_db.DB_PATH) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_incidents_started_at'"
            )
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_logs_indexes_still_exist(self, isolated_db):
        await isolated_db.init_db()
        async with aiosqlite.connect(isolated_db.DB_PATH) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_logs_ts'"
            )
            row = await cursor.fetchone()
            assert row is not None
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_logs_ep_ts'"
            )
            row = await cursor.fetchone()
            assert row is not None


class TestIdempotency:
    """Repeated init_db() calls must not fail."""

    @pytest.mark.asyncio
    async def test_repeated_init_db_does_not_fail(self, isolated_db):
        await isolated_db.init_db()
        await isolated_db.init_db()
        await isolated_db.init_db()

    @pytest.mark.asyncio
    async def test_repeated_init_db_preserves_data(self, isolated_db):
        await isolated_db.init_db()
        await isolated_db.insert_anomaly({
            "detected_at": "2024-01-01T00:00:00",
            "anomaly_type": "latency_spike",
            "severity": "high",
            "endpoint": "/api/test",
            "description": "test anomaly",
            "root_cause_chain": [],
            "suggested_fix": "check logs",
        })
        await isolated_db.init_db()
        anomalies = await isolated_db.get_recent_anomalies(10)
        assert len(anomalies) == 1
        assert anomalies[0]["endpoint"] == "/api/test"


class TestExistingDatabase:
    """Existing databases with data must continue working."""

    @pytest.mark.asyncio
    async def test_existing_db_with_data_continues_working(self, isolated_db):
        await isolated_db.init_db()
        await isolated_db.insert_anomaly({
            "detected_at": "2024-01-01T00:00:00",
            "anomaly_type": "error_surge",
            "severity": "critical",
            "endpoint": "/api/auth",
            "description": "high error rate",
            "root_cause_chain": [],
            "suggested_fix": "",
        })
        # Simulate app restart: init_db() on an existing DB
        await isolated_db.init_db()
        anomalies = await isolated_db.get_recent_anomalies(10)
        assert len(anomalies) == 1
        assert anomalies[0]["anomaly_type"] == "error_surge"

    @pytest.mark.asyncio
    async def test_existing_db_prune_still_works(self, isolated_db):
        await isolated_db.init_db()
        await isolated_db.insert_anomaly({
            "detected_at": "2024-01-01T00:00:00",
            "anomaly_type": "latency_spike",
            "severity": "low",
            "endpoint": "/api/health",
            "description": "old anomaly",
            "root_cause_chain": [],
            "suggested_fix": "",
        })
        await isolated_db.init_db()
        await isolated_db.prune_old_anomalies(minutes=0)
        anomalies = await isolated_db.get_recent_anomalies(10)
        assert len(anomalies) == 0