"""
Regression test for issue #72 — the three initial-state send_json calls on
WebSocket connect ran outside the try/except, so a client dropping mid-handshake
leaked the dead socket into manager.active and threw an unhandled error.

Driven with asyncio.run() (sync test) so it needs no pytest-asyncio plugin.
"""

import asyncio

from fastapi import WebSocketDisconnect

import main


class _FakeManager:
    def __init__(self):
        self.active = set()
        self.disconnected = []

    async def connect(self, ws):
        self.active.add(ws)

    def disconnect(self, ws):
        self.active.discard(ws)
        self.disconnected.append(ws)


class _FakeWS:
    """WebSocket stub that drops (raises WebSocketDisconnect) on the Nth send."""

    def __init__(self, fail_on_send=1):
        self.fail_on_send = fail_on_send
        self.sends = 0

    async def send_json(self, _msg):
        self.sends += 1
        if self.sends >= self.fail_on_send:
            raise WebSocketDisconnect()

    async def receive_text(self):
        raise WebSocketDisconnect()


def _patch(monkeypatch):
    mgr = _FakeManager()
    monkeypatch.setattr(main, "manager", mgr)
    monkeypatch.setattr(main, "get_health_snapshot", lambda: {})
    monkeypatch.setattr(main, "get_current_scenario", lambda: "normal")

    async def _no_anomalies(_n):
        return []

    monkeypatch.setattr(main, "get_recent_anomalies", _no_anomalies)
    return mgr


def test_disconnect_on_first_initial_send_is_handled(monkeypatch):
    """Client drops before the first init frame is delivered."""
    mgr = _patch(monkeypatch)
    ws = _FakeWS(fail_on_send=1)

    # Must not raise — the initial sends are now inside the try/except.
    asyncio.run(main.websocket_endpoint(ws))

    assert ws not in mgr.active, "dead socket leaked into manager.active"
    assert mgr.disconnected == [ws], "disconnect() was not called on the dropped socket"


def test_disconnect_on_later_initial_send_is_handled(monkeypatch):
    """Client survives the first frame but drops on the third."""
    mgr = _patch(monkeypatch)
    ws = _FakeWS(fail_on_send=3)

    asyncio.run(main.websocket_endpoint(ws))

    assert ws not in mgr.active
    assert mgr.disconnected == [ws]
