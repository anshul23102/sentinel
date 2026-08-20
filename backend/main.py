import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

load_dotenv()

from db import init_db, get_recent_logs, get_recent_anomalies, get_endpoint_stats, get_timeseries, insert_anomaly, prune_old_logs, upsert_seasonal_bucket, delete_session_data
from log_generator import run_generator, set_scenario, get_current_scenario, SCENARIOS, SIM_DAY_SECONDS, BUCKETS_PER_DAY
from anomaly_detector import process_log_batch, get_health_snapshot, run_anomaly_scan
from ai_agent import analyze_anomaly, chat, chat_stream, generate_incident_report
from ratelimit import rate_limit, require_api_key
import session_manager
import state

BUCKET_SECONDS = SIM_DAY_SECONDS // BUCKETS_PER_DAY

# WebSocket connection manager — keyed by session, so a broadcast for one
# visitor's simulated world only ever reaches that visitor's own tabs.
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, sid: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(sid, []).append(ws)

    def disconnect(self, sid: str, ws: WebSocket):
        if sid in self.active and ws in self.active[sid]:
            self.active[sid].remove(ws)
            if not self.active[sid]:
                del self.active[sid]

    async def broadcast(self, sid: str, message: dict):
        """Send concurrently, not one-by-one — a sequential loop lets dead
        connections stack: if N dead sockets each burn the timeout, a single
        broadcast can take N*timeout, and since log_pipeline calls broadcast
        every second, ticks pile up faster than they drain and peg the CPU."""
        conns = self.active.get(sid)
        if not conns:
            return

        async def _send(ws: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(ws.send_json(message), timeout=1)
                return None
            except Exception:
                return ws

        results = await asyncio.gather(*(_send(ws) for ws in conns))
        for ws in results:
            if ws is not None:
                self.disconnect(sid, ws)

manager = ConnectionManager()

# ── Session identity ────────────────────────────────────────────────────────
async def get_session_id(x_session_id: Optional[str] = Header(None)) -> str:
    """Every REST call and WebSocket connection resolves to a session id.
    The frontend generates one UUID per browser and sends it on every
    request; a caller with no header (curl, a fresh test) gets a fresh
    ephemeral session rather than falling into one shared global world."""
    sid = x_session_id or str(uuid.uuid4())
    await _ensure_session(sid)
    session_manager.touch(sid)
    return sid

async def _ensure_session(sid: str):
    async def _start() -> list[asyncio.Task]:
        return [
            asyncio.create_task(log_pipeline(sid)),
            asyncio.create_task(periodic_scan(sid)),
        ]
    await session_manager.ensure_running(sid, _start)

# ── Background pipeline (per session) ───────────────────────────────────────
async def log_pipeline(sid: str):
    """One session's pipeline: generate logs → detect anomalies → broadcast,
    scoped entirely to that session's own simulated world."""
    async def broadcast_and_detect(message: dict):
        if message["type"] == "logs":
            new_anomalies = await process_log_batch(sid, message["data"])
            for anomaly in new_anomalies:
                # Insert FIRST so anomaly has an ID before AI analysis references it
                anomaly_id     = await insert_anomaly(sid, anomaly)
                anomaly["id"]  = anomaly_id
                await manager.broadcast(sid, {"type": "anomaly", "data": anomaly})
                # Non-blocking AI analysis — ID is already in anomaly dict
                task = asyncio.create_task(_async_ai_analysis(sid, anomaly))
                task.add_done_callback(
                    lambda t: t.exception() and print(f"[AI] Analysis task failed: {t.exception()}")
                )
        await manager.broadcast(sid, message)

    await run_generator(sid, broadcast_and_detect, rps=30)

async def _async_ai_analysis(sid: str, anomaly: dict):
    """Run AI root cause analysis in background and broadcast result."""
    try:
        recent_logs = await get_recent_logs(sid, 120, anomaly["endpoint"])
        result      = await analyze_anomaly(sid, anomaly, recent_logs)
        await manager.broadcast(sid, {"type": "ai_analysis", "data": result})
    except Exception as e:
        print(f"[AI] Analysis failed for {anomaly.get('endpoint')}: {e}")

async def periodic_scan(sid: str):
    """Every 5s, for one session: run anomaly scan, broadcast health, prune
    old rows, and record the current seasonal bucket."""
    tick = 0
    while True:
        await asyncio.sleep(5)
        tick += 1
        await run_anomaly_scan(sid, lambda m: manager.broadcast(sid, m))
        health = await get_health_snapshot(sid)
        await manager.broadcast(sid, {"type": "health", "data": health})
        # Prune logs older than 15 minutes every 60s to keep DB lean
        if tick % 12 == 0:
            await prune_old_logs(sid, minutes=15)

        # Record the current bucket from the actual per-tick feature window,
        # not the health snapshot's rolling-window sample_size — that caps at
        # 60 once the window fills, so it can never reflect real traffic volume.
        bucket_index = int(time.time() // BUCKET_SECONDS)
        for endpoint in health:
            feature_row = await state.get_feature_window(sid, endpoint)
            if feature_row:
                avg_latency, error_rate, req_count = feature_row[-1]
                await upsert_seasonal_bucket(sid, endpoint, bucket_index, avg_latency, error_rate, req_count)

async def _cleanup_session(sid: str):
    print(f"[session] reaping idle session {sid}", flush=True)
    await delete_session_data(sid)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    asyncio.create_task(session_manager.reaper_loop(_cleanup_session))
    yield

app = FastAPI(title="Sentinel — API Intelligence Platform", lifespan=lifespan)

# CORS_ORIGINS: comma-separated allowlist. Defaults to local dev only —
# a deployed frontend must set this explicitly rather than relying on "*",
# which allows any site on the internet to call this API from a browser.
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST endpoints
@app.get("/api/health")
async def health(sid: str = Depends(get_session_id)):
    return await get_health_snapshot(sid)

@app.get("/api/logs")
async def logs(limit: int = 100, endpoint: Optional[str] = None, sid: str = Depends(get_session_id)):
    return await get_recent_logs(sid, limit, endpoint)

@app.get("/api/anomalies")
async def anomalies(limit: int = 20, sid: str = Depends(get_session_id)):
    return await get_recent_anomalies(sid, limit)

@app.get("/api/stats")
async def stats(minutes: int = 5, sid: str = Depends(get_session_id)):
    return await get_endpoint_stats(sid, minutes)

@app.get("/api/timeseries")
async def timeseries(minutes: int = 10, sid: str = Depends(get_session_id)):
    return await get_timeseries(sid, minutes)

@app.get("/api/scenario")
async def get_scenario(sid: str = Depends(get_session_id)):
    return {"current": await get_current_scenario(sid), "available": list(SCENARIOS.keys())}

class ScenarioRequest(BaseModel):
    scenario: str
    intensity: float = 1.0

@app.post("/api/scenario", dependencies=[Depends(rate_limit("scenario", limit=20, window_seconds=60)), Depends(require_api_key)])
async def inject_scenario(req: ScenarioRequest, sid: str = Depends(get_session_id)):
    if req.scenario not in SCENARIOS:
        raise HTTPException(400, f"Unknown scenario. Valid: {list(SCENARIOS.keys())}")
    await set_scenario(sid, req.scenario, req.intensity)
    await manager.broadcast(sid, {
        "type": "scenario_change",
        "data": {
            "scenario":    req.scenario,
            "description": SCENARIOS[req.scenario]["description"],
            "intensity":   req.intensity,
        }
    })
    return {"status": "ok", "scenario": req.scenario}

class ChatRequest(BaseModel):
    message: str = Field(..., max_length=2000)
    history: list[dict] = []

@app.post("/api/chat", dependencies=[Depends(rate_limit("chat", limit=10, window_seconds=60)), Depends(require_api_key)])
async def chat_endpoint(req: ChatRequest, sid: str = Depends(get_session_id)):
    response = await chat(sid, req.message, req.history)
    return {"response": response}

@app.post("/api/chat/stream", dependencies=[Depends(rate_limit("chat", limit=10, window_seconds=60)), Depends(require_api_key)])
async def chat_stream_endpoint(req: ChatRequest, sid: str = Depends(get_session_id)):
    """Server-Sent Events streaming chat — tokens arrive as they're generated."""
    async def event_generator():
        try:
            async for chunk in chat_stream(sid, req.message, req.history):
                # SSE format: data: <text>\n\n
                yield f"data: {json.dumps({'token': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",
        }
    )

@app.post("/api/incident-report", dependencies=[Depends(rate_limit("incident-report", limit=5, window_seconds=60)), Depends(require_api_key)])
async def incident_report(sid: str = Depends(get_session_id)):
    anomalies_data = await get_recent_anomalies(sid, 20)
    if not anomalies_data:
        return {"report": "No anomalies detected in the current monitoring window."}
    report = await generate_incident_report(anomalies_data, 10)
    return {"report": report}

# WebSocket
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, session: Optional[str] = None):
    sid = session or str(uuid.uuid4())
    await _ensure_session(sid)
    session_manager.connection_opened(sid)
    await manager.connect(sid, ws)
    try:
        # Push current state immediately on connect — a client that disconnects
        # mid-handshake can throw here too, so this must be inside the same
        # try/finally as the main loop or the connection never gets cleaned up
        # and becomes a permanent zombie in manager.active.
        health          = await get_health_snapshot(sid)
        recent_anomalies = await get_recent_anomalies(sid, 10)
        await ws.send_json({"type": "session",          "data": {"session_id": sid}})
        await ws.send_json({"type": "health",          "data": health})
        await ws.send_json({"type": "init_anomalies",  "data": recent_anomalies})
        await ws.send_json({"type": "scenario_change", "data": {"scenario": await get_current_scenario(sid)}})
        while True:
            try:
                await ws.receive_text()  # keep-alive / ping
                session_manager.touch(sid)
            except WebSocketDisconnect:
                raise
            except Exception:
                pass  # ignore malformed frames — only WebSocketDisconnect exits the loop
    except Exception:
        pass
    finally:
        manager.disconnect(sid, ws)
        session_manager.connection_closed(sid)
