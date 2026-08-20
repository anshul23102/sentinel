import os
import json
import redis.asyncio as redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

WINDOW_MAXLEN  = 60     # matches the 60s sliding window the detector uses
SESSION_TTL    = 1800   # 30 min — every session key gets this TTL refreshed on
                        # write, so an abandoned session's Redis footprint
                        # self-cleans even if the reaper task's cancel logic
                        # ever has a bug. Defense in depth, not the primary
                        # cleanup mechanism.

_client: redis.Redis | None = None

def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client

def _k(sid: str, *parts: str) -> str:
    return "sentinel:" + sid + ":" + ":".join(parts)

def latency_key(sid: str, endpoint: str) -> str:
    return _k(sid, "win", "latency", endpoint)

def error_key(sid: str, endpoint: str) -> str:
    return _k(sid, "win", "errors", endpoint)

async def push_window(sid: str, key: str, value: float, endpoint: str) -> None:
    """Append to a capped sliding window, tracking the endpoint so health
    snapshots can enumerate every endpoint this session has ever reported."""
    c = get_client()
    async with c.pipeline(transaction=True) as pipe:
        pipe.rpush(key, value)
        pipe.ltrim(key, -WINDOW_MAXLEN, -1)
        pipe.expire(key, SESSION_TTL)
        pipe.sadd(_k(sid, "known_endpoints"), endpoint)
        pipe.expire(_k(sid, "known_endpoints"), SESSION_TTL)
        await pipe.execute()

async def get_window(key: str) -> list[float]:
    c = get_client()
    raw = await c.lrange(key, 0, -1)
    return [float(v) for v in raw]

async def get_known_endpoints(sid: str) -> list[str]:
    c = get_client()
    return list(await c.smembers(_k(sid, "known_endpoints")))

async def push_feature_row(sid: str, endpoint: str, row: list[float]) -> None:
    """One row per tick: [avg_latency, error_rate, req_count] — the feature
    vector the multivariate (Isolation Forest) detector trains and scores on."""
    c = get_client()
    key = _k(sid, "win", "features", endpoint)
    async with c.pipeline(transaction=True) as pipe:
        pipe.rpush(key, json.dumps(row))
        pipe.ltrim(key, -WINDOW_MAXLEN, -1)
        pipe.expire(key, SESSION_TTL)
        await pipe.execute()

async def get_feature_window(sid: str, endpoint: str) -> list[list[float]]:
    c = get_client()
    raw = await c.lrange(_k(sid, "win", "features", endpoint), 0, -1)
    return [json.loads(v) for v in raw]

async def get_active_anomaly(sid: str, key: str) -> dict | None:
    c = get_client()
    raw = await c.get(_k(sid, "active", key))
    return json.loads(raw) if raw else None

async def set_active_anomaly(sid: str, key: str, value: dict) -> None:
    c = get_client()
    await c.set(_k(sid, "active", key), json.dumps(value), ex=SESSION_TTL)

async def clear_active_anomaly(sid: str, key: str) -> None:
    c = get_client()
    await c.delete(_k(sid, "active", key))

async def get_scenario(sid: str) -> dict:
    c = get_client()
    current, intensity, start_time = await c.mget(
        _k(sid, "scenario", "current"),
        _k(sid, "scenario", "intensity"),
        _k(sid, "scenario", "start_time"),
    )
    return {
        "current":    current or "normal",
        "intensity":  float(intensity) if intensity else 1.0,
        "start_time": float(start_time) if start_time else 0.0,
    }

async def set_scenario(sid: str, name: str, intensity: float, start_time: float) -> None:
    c = get_client()
    async with c.pipeline(transaction=True) as pipe:
        pipe.mset({
            _k(sid, "scenario", "current"):    name,
            _k(sid, "scenario", "intensity"):  str(intensity),
            _k(sid, "scenario", "start_time"): str(start_time),
        })
        pipe.expire(_k(sid, "scenario", "current"), SESSION_TTL)
        pipe.expire(_k(sid, "scenario", "intensity"), SESSION_TTL)
        pipe.expire(_k(sid, "scenario", "start_time"), SESSION_TTL)
        await pipe.execute()

async def touch_session(sid: str) -> None:
    """Refresh the last-active heartbeat used by the reaper to find idle sessions."""
    c = get_client()
    await c.set(_k(sid, "heartbeat"), "1", ex=SESSION_TTL)

async def session_alive(sid: str) -> bool:
    c = get_client()
    return await c.exists(_k(sid, "heartbeat")) > 0
