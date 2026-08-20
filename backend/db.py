import os
import json
import asyncpg
from datetime import datetime, timedelta, timezone

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/sentinel")

_pool: asyncpg.Pool | None = None

async def init_db():
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id BIGSERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                latency_ms DOUBLE PRECISION NOT NULL,
                error_message TEXT,
                service TEXT NOT NULL,
                user_id TEXT,
                metadata JSONB
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id BIGSERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                anomaly_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                description TEXT NOT NULL,
                root_cause_chain JSONB,
                suggested_fix TEXT,
                resolved INTEGER DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id BIGSERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                root_cause TEXT,
                impact TEXT,
                affected_endpoints TEXT
            )
        """)
        # Downsampled rollup for the seasonal (Holt-Winters) baseline — raw
        # logs get pruned every 15 minutes, but the seasonal model needs
        # history spanning multiple simulated days, so this keeps one small
        # aggregate row per session per endpoint per bucket.
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS seasonal_buckets (
                session_id TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                bucket_index BIGINT NOT NULL,
                avg_latency DOUBLE PRECISION NOT NULL,
                error_rate DOUBLE PRECISION NOT NULL,
                req_count DOUBLE PRECISION NOT NULL,
                recorded_at TEXT NOT NULL,
                PRIMARY KEY (session_id, endpoint, bucket_index)
            )
        """)
        # Migration for pre-existing installs: add session_id to tables that
        # predate multi-tenancy, backfilling old rows into one 'legacy' bucket.
        for table in ("logs", "anomalies", "incidents"):
            await conn.execute(f"""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = '{table}' AND column_name = 'session_id'
                    ) THEN
                        ALTER TABLE {table} ADD COLUMN session_id TEXT NOT NULL DEFAULT 'legacy';
                    END IF;
                END $$;
            """)
        # Indexes for the hot query paths — session_id first, since every
        # query now filters on it before anything else.
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_sid_ts ON logs(session_id, timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_sid_ep_ts ON logs(session_id, endpoint, timestamp)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_sid ON anomalies(session_id, detected_at)")

def _cutoff(minutes: int) -> str:
    """Compute the ISO timestamp cutoff in Python, not SQL — keeps queries DB-agnostic."""
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%S")

async def bulk_insert_logs(session_id: str, logs: list[dict]):
    """Insert multiple logs in a single transaction for performance."""
    async with _pool.acquire() as conn:
        await conn.executemany("""
            INSERT INTO logs (session_id, timestamp, endpoint, method, status_code, latency_ms, error_message, service, user_id, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """, [
            (
                session_id, log["timestamp"], log["endpoint"], log["method"],
                log["status_code"], log["latency_ms"], log.get("error_message"),
                log["service"], log.get("user_id"), json.dumps(log.get("metadata", {}))
            )
            for log in logs
        ])

async def insert_anomaly(session_id: str, anomaly: dict) -> int:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO anomalies (session_id, detected_at, anomaly_type, severity, endpoint, description, root_cause_chain, suggested_fix)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """,
            session_id, anomaly["detected_at"], anomaly["anomaly_type"], anomaly["severity"],
            anomaly["endpoint"], anomaly["description"],
            json.dumps(anomaly.get("root_cause_chain", [])),
            anomaly.get("suggested_fix", "")
        )
        return row["id"]

async def get_recent_logs(session_id: str, limit: int = 200, endpoint: str = None):
    async with _pool.acquire() as conn:
        if endpoint:
            rows = await conn.fetch(
                "SELECT * FROM logs WHERE session_id = $1 AND endpoint = $2 ORDER BY timestamp DESC LIMIT $3",
                session_id, endpoint, limit
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM logs WHERE session_id = $1 ORDER BY timestamp DESC LIMIT $2", session_id, limit
            )
        return [dict(r) for r in rows]

async def get_recent_anomalies(session_id: str, limit: int = 20):
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM anomalies WHERE session_id = $1 ORDER BY detected_at DESC LIMIT $2", session_id, limit
        )
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["root_cause_chain"] = json.loads(d["root_cause_chain"] or "[]")
            except (json.JSONDecodeError, TypeError):
                d["root_cause_chain"] = []
            result.append(d)
        return result

async def get_endpoint_stats(session_id: str, minutes: int = 5):
    async with _pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                endpoint,
                COUNT(*) as total_requests,
                AVG(latency_ms) as avg_latency,
                MAX(latency_ms) as max_latency,
                SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) as error_5xx,
                SUM(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 ELSE 0 END) as error_4xx,
                SUM(CASE WHEN status_code < 400 THEN 1 ELSE 0 END) as success_count
            FROM logs
            WHERE session_id = $1 AND timestamp >= $2
            GROUP BY endpoint
            ORDER BY total_requests DESC
        """, session_id, _cutoff(minutes))
        return [dict(r) for r in rows]

async def prune_old_logs(session_id: str, minutes: int = 15):
    """Keep the DB lean — delete this session's logs older than `minutes`."""
    async with _pool.acquire() as conn:
        await conn.execute("DELETE FROM logs WHERE session_id = $1 AND timestamp < $2", session_id, _cutoff(minutes))

async def get_timeseries(session_id: str, minutes: int = 10):
    async with _pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                timestamp as second,
                AVG(latency_ms) as avg_latency,
                COUNT(*) as req_count,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors
            FROM logs
            WHERE session_id = $1 AND timestamp >= $2
            GROUP BY timestamp
            ORDER BY timestamp ASC
        """, session_id, _cutoff(minutes))
        return [dict(r) for r in rows]

async def upsert_seasonal_bucket(session_id: str, endpoint: str, bucket_index: int, avg_latency: float, error_rate: float, req_count: float):
    async with _pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO seasonal_buckets (session_id, endpoint, bucket_index, avg_latency, error_rate, req_count, recorded_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (session_id, endpoint, bucket_index)
            DO UPDATE SET avg_latency = $4, error_rate = $5, req_count = $6
        """, session_id, endpoint, bucket_index, avg_latency, error_rate, req_count,
             datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))

async def get_seasonal_history(session_id: str, endpoint: str, limit: int = 200) -> list[float]:
    """Ordered avg_latency series for the seasonal baseline fit — oldest first."""
    async with _pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT avg_latency FROM seasonal_buckets
            WHERE session_id = $1 AND endpoint = $2
            ORDER BY bucket_index DESC
            LIMIT $3
        """, session_id, endpoint, limit)
        return [r["avg_latency"] for r in reversed(rows)]

async def delete_session_data(session_id: str):
    """Called when a session is reaped for inactivity — drops its rows so a
    public multi-tenant demo doesn't accumulate abandoned sessions' data
    forever in Postgres the way the old single-tenant prune never had to."""
    async with _pool.acquire() as conn:
        await conn.execute("DELETE FROM logs WHERE session_id = $1", session_id)
        await conn.execute("DELETE FROM anomalies WHERE session_id = $1", session_id)
        await conn.execute("DELETE FROM seasonal_buckets WHERE session_id = $1", session_id)
