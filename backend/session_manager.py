"""Per-session lifecycle: each visitor gets their own isolated simulated
world (traffic generator, detector state, scenario control) instead of one
process-global shared world that every visitor collided in. A session's
background tasks start on first contact and stop after it's been idle with
zero open connections for a while — a public demo link accumulates visitors
who never come back, and their tasks/data shouldn't run and grow forever.
"""
import asyncio
import time

IDLE_TIMEOUT = 300  # 5 min with zero WebSocket connections before reaping

_sessions: dict[str, dict] = {}  # sid -> {"tasks": [Task], "connections": int, "last_active": float}


def _entry(sid: str) -> dict:
    if sid not in _sessions:
        _sessions[sid] = {"tasks": [], "connections": 0, "last_active": time.time()}
    return _sessions[sid]


def touch(sid: str) -> None:
    """Call on every REST request too, not just WebSocket activity — an
    actively-chatting-but-no-open-tab session shouldn't get reaped either."""
    _entry(sid)["last_active"] = time.time()


async def ensure_running(sid: str, start_fn) -> None:
    """Idempotent: starts this session's background tasks (log generator +
    periodic scan) if they aren't already running. `start_fn` is an async
    callable returning the list of asyncio.Task objects to track."""
    entry = _entry(sid)
    entry["last_active"] = time.time()
    if not entry["tasks"]:
        entry["tasks"] = await start_fn()


def connection_opened(sid: str) -> None:
    entry = _entry(sid)
    entry["connections"] += 1
    entry["last_active"] = time.time()


def connection_closed(sid: str) -> None:
    if sid in _sessions:
        _sessions[sid]["connections"] = max(0, _sessions[sid]["connections"] - 1)
        _sessions[sid]["last_active"] = time.time()


async def reaper_loop(cleanup_fn, poll_interval: float = 30) -> None:
    """Every `poll_interval` seconds, cancel and drop any session with zero
    open WebSocket connections that's been idle past IDLE_TIMEOUT.
    `cleanup_fn(sid)` deletes that session's Postgres rows (Redis keys expire
    on their own via TTL)."""
    while True:
        await asyncio.sleep(poll_interval)
        now = time.time()
        for sid in list(_sessions.keys()):
            entry = _sessions[sid]
            if entry["connections"] == 0 and now - entry["last_active"] > IDLE_TIMEOUT:
                for t in entry["tasks"]:
                    t.cancel()
                del _sessions[sid]
                await cleanup_fn(sid)


def active_session_count() -> int:
    return len(_sessions)
