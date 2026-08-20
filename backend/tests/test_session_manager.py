import asyncio
import uuid
import pytest
import session_manager


@pytest.mark.asyncio
async def test_ensure_running_is_idempotent():
    sid = f"test-{uuid.uuid4()}"
    calls = 0
    async def start():
        nonlocal calls
        calls += 1
        return [asyncio.create_task(asyncio.sleep(10))]

    await session_manager.ensure_running(sid, start)
    await session_manager.ensure_running(sid, start)
    assert calls == 1  # second call is a no-op — tasks already running

    for t in session_manager._sessions[sid]["tasks"]:
        t.cancel()
    del session_manager._sessions[sid]


@pytest.mark.asyncio
async def test_reaper_cancels_idle_session_with_zero_connections(monkeypatch):
    monkeypatch.setattr(session_manager, "IDLE_TIMEOUT", 0.2)
    sid = f"test-{uuid.uuid4()}"
    ran = {"alive": True}

    async def loop_task():
        try:
            while True:
                await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            ran["alive"] = False
            raise

    await session_manager.ensure_running(sid, lambda: _wrap_task(loop_task))

    cleaned = []
    async def cleanup_fn(s):
        cleaned.append(s)

    reaper = asyncio.create_task(session_manager.reaper_loop(cleanup_fn, poll_interval=0.1))
    await asyncio.sleep(0.6)
    reaper.cancel()

    assert sid in cleaned
    assert sid not in session_manager._sessions


async def _wrap_task(coro_fn):
    return [asyncio.create_task(coro_fn())]


@pytest.mark.asyncio
async def test_reaper_preserves_session_with_open_connection(monkeypatch):
    monkeypatch.setattr(session_manager, "IDLE_TIMEOUT", 0.2)
    sid = f"test-{uuid.uuid4()}"

    async def loop_task():
        while True:
            await asyncio.sleep(0.02)

    await session_manager.ensure_running(sid, lambda: _wrap_task(loop_task))
    session_manager.connection_opened(sid)

    cleaned = []
    async def cleanup_fn(s):
        cleaned.append(s)

    reaper = asyncio.create_task(session_manager.reaper_loop(cleanup_fn, poll_interval=0.1))
    await asyncio.sleep(0.6)
    reaper.cancel()

    assert sid not in cleaned
    assert sid in session_manager._sessions

    for t in session_manager._sessions[sid]["tasks"]:
        t.cancel()
    del session_manager._sessions[sid]
