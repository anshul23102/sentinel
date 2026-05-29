import aiosqlite
import json
from datetime import datetime

DB_PATH = "api_logs.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # WAL mode: allows concurrent reads during writes (critical for 1s bulk insert cadence)
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")   # safe with WAL, much faster than FULL
        await db.execute("PRAGMA cache_size=-8000")     # 8MB page cache
        await db.execute("PRAGMA temp_store=MEMORY")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                latency_ms REAL NOT NULL,
                error_message TEXT,
                service TEXT NOT NULL,
                user_id TEXT,
                metadata TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detected_at TEXT NOT NULL,
                anomaly_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                description TEXT NOT NULL,
                root_cause_chain TEXT,
                suggested_fix TEXT,
                resolved INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                root_cause TEXT,
                impact TEXT,
                affected_endpoints TEXT
            )
        """)
        # Indexes for the hot query paths
        await db.execute("CREATE INDEX IF NOT EXISTS idx_logs_ts ON logs(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_logs_ep_ts ON logs(endpoint, timestamp)")
        await db.commit()

async def insert_log(log: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO logs (timestamp, endpoint, method, status_code, latency_ms, error_message, service, user_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log["timestamp"], log["endpoint"], log["method"],
            log["status_code"], log["latency_ms"], log.get("error_message"),
            log["service"], log.get("user_id"), json.dumps(log.get("metadata", {}))
        ))
        await db.commit()

async def bulk_insert_logs(logs: list[dict]):
    """Insert multiple logs in a single transaction for performance."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany("""
            INSERT INTO logs (timestamp, endpoint, method, status_code, latency_ms, error_message, service, user_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                log["timestamp"], log["endpoint"], log["method"],
                log["status_code"], log["latency_ms"], log.get("error_message"),
                log["service"], log.get("user_id"), json.dumps(log.get("metadata", {}))
            )
            for log in logs
        ])
        await db.commit()

async def insert_anomaly(anomaly: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO anomalies (detected_at, anomaly_type, severity, endpoint, description, root_cause_chain, suggested_fix)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            anomaly["detected_at"], anomaly["anomaly_type"], anomaly["severity"],
            anomaly["endpoint"], anomaly["description"],
            json.dumps(anomaly.get("root_cause_chain", [])),
            anomaly.get("suggested_fix", "")
        ))
        await db.commit()
        return cursor.lastrowid

async def get_recent_logs(limit: int = 200, endpoint: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if endpoint:
            cursor = await db.execute(
                "SELECT * FROM logs WHERE endpoint = ? ORDER BY timestamp DESC LIMIT ?",
                (endpoint, limit)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def get_recent_anomalies(limit: int = 20):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM anomalies ORDER BY detected_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["root_cause_chain"] = json.loads(d["root_cause_chain"] or "[]")
            except (json.JSONDecodeError, TypeError):
                d["root_cause_chain"] = []
            result.append(d)
        return result

async def get_endpoint_stats(minutes: int = 5):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT
                endpoint,
                COUNT(*) as total_requests,
                AVG(latency_ms) as avg_latency,
                MAX(latency_ms) as max_latency,
                SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) as error_5xx,
                SUM(CASE WHEN status_code >= 400 AND status_code < 500 THEN 1 ELSE 0 END) as error_4xx,
                SUM(CASE WHEN status_code < 400 THEN 1 ELSE 0 END) as success_count
            FROM logs
            WHERE timestamp >= datetime('now', ? || ' minutes')
            GROUP BY endpoint
            ORDER BY total_requests DESC
        """, (f"-{minutes}",))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def prune_old_logs(minutes: int = 15):
    """Keep DB lean — delete logs older than `minutes` to prevent unbounded growth."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM logs WHERE timestamp < datetime('now', ? || ' minutes')",
            (f"-{minutes}",)
        )
        await db.commit()

async def get_timeseries(minutes: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT
                strftime('%Y-%m-%dT%H:%M:%S', timestamp) as second,
                AVG(latency_ms) as avg_latency,
                COUNT(*) as req_count,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors
            FROM logs
            WHERE timestamp >= datetime('now', ? || ' minutes')
            GROUP BY strftime('%Y-%m-%dT%H:%M:%S', timestamp)
            ORDER BY second ASC
        """, (f"-{minutes}",))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
