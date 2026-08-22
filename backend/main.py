import asyncio
import csv
import io
import json
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

load_dotenv()

from db import init_db, get_recent_logs, get_recent_anomalies, get_endpoint_stats, get_timeseries, insert_anomaly, prune_old_logs, prune_old_anomalies, upsert_seasonal_bucket, delete_session_data  # noqa: E402
from log_generator import run_generator, set_scenario, get_current_scenario, SCENARIOS, SIM_DAY_SECONDS, BUCKETS_PER_DAY  # noqa: E402
from anomaly_detector import process_log_batch, get_health_snapshot, run_anomaly_scan  # noqa: E402
from ai_agent import analyze_anomaly, chat, chat_stream, generate_incident_report  # noqa: E402
from ratelimit import rate_limit, require_api_key  # noqa: E402
from task_supervisor import TaskSupervisor, SupervisorConfig  # noqa: E402
import session_manager  # noqa: E402
import state  # noqa: E402

BUCKET_SECONDS = SIM_DAY_SECONDS // BUCKETS_PER_DAY

# Synthetic traffic rate per session's log_pipeline. 30 rps is the real
# demo/production rate. Every unique session id — including a throwaway one
# a test creates just to check an HTTP status code — runs this generator
# continuously in the background until reaped, so a low-traffic environment
# like CI (a handful of concurrently-active sessions, but each generating
# real Redis writes at full rate) benefits from being able to turn this
# down without changing the actual demo experience for real visitors.
LOG_RPS = int(os.environ.get("SENTINEL_LOG_RPS", "30"))

# One supervisor for every session's background tasks — register()/start_task()
# per session with a unique name, stop_task() on reap. Auto-restarts a crashed
# log_pipeline/periodic_scan with exponential backoff instead of leaving that
# session's simulated world silently dead until the whole process restarts.
supervisor = TaskSupervisor(SupervisorConfig(initial_backoff=1.0, max_backoff=60.0, backoff_multiplier=2.0))

# Per-session "did the pipeline actually complete a cycle recently" — surfaced
# on /api/health so a stuck-but-not-crashed pipeline is visible, not just a
# crashed one (which the supervisor's own status already covers).
_last_monitoring_cycle: dict[str, float] = {}

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
# A caller can put whatever string it wants in X-Session-Id — the frontend
# always sends a crypto.randomUUID(), but nothing on the wire enforces that.
# Bound the shape so a hostile caller can't hand this process an arbitrarily
# large or control-character-laden key that ends up embedded in Redis keys
# and Postgres rows on every downstream write.
_SID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

# Every unauthenticated caller can mint a brand-new session id and get one
# for free — that's the point, for anonymous demo visitors. But an unbounded
# rate of *new* sessions each spins up its own traffic generator + detector
# background tasks and Postgres/Redis footprint, so without a limit here a
# single script looping with a fresh id per request exhausts the process
# long before the idle reaper (session_manager.IDLE_TIMEOUT) ever runs.
# This only throttles *creating* a new world — a returning visitor touching
# their existing session is never rate-limited by it.
_new_session_rate_limit = rate_limit("new_session", limit=10, window_seconds=60)

async def get_session_id(request: Request, x_session_id: Optional[str] = Header(None)) -> str:
    """Every REST call and WebSocket connection resolves to a session id.
    The frontend generates one UUID per browser and sends it on every
    request; a caller with no header (curl, a fresh test) gets a fresh
    ephemeral session rather than falling into one shared global world."""
    sid = x_session_id or str(uuid.uuid4())
    if not _SID_PATTERN.match(sid):
        raise HTTPException(400, "Invalid session id")
    if not session_manager.session_exists(sid):
        await _new_session_rate_limit(request)
    try:
        await _ensure_session(sid)
    except session_manager.CapacityExceeded:
        raise HTTPException(503, "Sentinel is at capacity — please try again shortly")
    session_manager.touch(sid)
    return sid

async def _ensure_session(sid: str):
    async def _start() -> list[asyncio.Task]:
        supervisor.register(f"log_pipeline:{sid}", lambda: log_pipeline(sid))
        supervisor.register(f"periodic_scan:{sid}", lambda: periodic_scan(sid))
        await supervisor.start_task(f"log_pipeline:{sid}")
        await supervisor.start_task(f"periodic_scan:{sid}")
        return [
            supervisor._tasks[f"log_pipeline:{sid}"].task,
            supervisor._tasks[f"periodic_scan:{sid}"].task,
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

    await run_generator(sid, broadcast_and_detect, rps=LOG_RPS)

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
        _last_monitoring_cycle[sid] = time.time()
        # Prune old rows every 60s to keep the DB lean: logs (15 min) and
        # the anomalies table (24h), which otherwise grows unbounded for
        # any session that stays alive longer than the reaper's idle timeout.
        if tick % 12 == 0:
            await prune_old_logs(sid, minutes=15)
            await prune_old_anomalies(sid, minutes=1440)

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
    # session_manager's reaper already cancelled the raw tasks directly —
    # this just unregisters them from the supervisor too, so a reaped
    # session's entries don't linger in supervisor._tasks forever.
    await supervisor.stop_task(f"log_pipeline:{sid}")
    await supervisor.stop_task(f"periodic_scan:{sid}")
    _last_monitoring_cycle.pop(sid, None)
    await delete_session_data(sid)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    asyncio.create_task(session_manager.reaper_loop(_cleanup_session))
    try:
        yield
    finally:
        await supervisor.shutdown()

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
# GET routes are read-only but were previously completely unguarded — no
# auth, no rate limit — while every mutating/AI-cost route already had one.
# A generous per-IP limit here still stops unbounded scraping/DoS without
# affecting normal dashboard polling (the WebSocket carries most live
# updates; these are occasional fetches, not a tight poll loop).
@app.get("/api/health", dependencies=[Depends(rate_limit("health", limit=120, window_seconds=60))])
async def health(sid: str = Depends(get_session_id)):
    health_data = dict(await get_health_snapshot(sid))
    pipeline_status = supervisor.get_task_status(f"log_pipeline:{sid}")
    scan_status     = supervisor.get_task_status(f"periodic_scan:{sid}")
    health_data["_monitoring"] = {
        "connected_websocket_clients": len(manager.active.get(sid, [])),
        "last_monitoring_cycle": _last_monitoring_cycle.get(sid),
        "log_pipeline_running": pipeline_status.get("running", False),
        "anomaly_detector_running": scan_status.get("running", False),
    }
    return health_data

@app.get("/api/logs", dependencies=[Depends(rate_limit("logs", limit=60, window_seconds=60))])
async def logs(limit: int = 100, endpoint: Optional[str] = None, sid: str = Depends(get_session_id)):
    return await get_recent_logs(sid, limit, endpoint)

@app.get("/api/anomalies", dependencies=[Depends(rate_limit("anomalies", limit=60, window_seconds=60))])
async def anomalies(limit: int = 20, sid: str = Depends(get_session_id)):
    return await get_recent_anomalies(sid, limit)

@app.get("/api/stats", dependencies=[Depends(rate_limit("stats", limit=60, window_seconds=60))])
async def stats(minutes: int = 5, sid: str = Depends(get_session_id)):
    return await get_endpoint_stats(sid, minutes)

@app.get("/api/timeseries", dependencies=[Depends(rate_limit("timeseries", limit=60, window_seconds=60))])
async def timeseries(minutes: int = 10, sid: str = Depends(get_session_id)):
    return await get_timeseries(sid, minutes)

@app.get("/api/scenario", dependencies=[Depends(rate_limit("scenario-get", limit=60, window_seconds=60))])
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

@app.get("/api/incidents/export", dependencies=[Depends(rate_limit("export", limit=10, window_seconds=60))])
async def export_incidents(format: str = "csv", limit: int = 1000, sid: str = Depends(get_session_id)):
    # Bound the export so it can't materialize an unbounded result — same
    # clamp db.py applies at the query boundary, enforced again here since
    # `limit` is a raw query param.
    limit = max(1, min(limit, 10000))
    incidents = await get_recent_anomalies(sid, limit)

    if format.lower() == "json":
        content = json.dumps(incidents, indent=2, default=str)
        return StreamingResponse(
            io.StringIO(content),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=sentinel_incidents.json"},
        )

    output = io.StringIO()
    if incidents:
        # root_cause_chain is a list (already parsed by get_recent_anomalies)
        # — flatten it to a string so it fits a CSV cell instead of breaking
        # the writer on a non-scalar value.
        rows = [{**row, "root_cause_chain": json.dumps(row.get("root_cause_chain", []))} for row in incidents]
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    else:
        output.write("No incidents found")
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sentinel_incidents.csv"},
    )

# WebSocket
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, session: Optional[str] = None):
    sid = session or str(uuid.uuid4())
    if not _SID_PATTERN.match(sid):
        await ws.close(code=1008)  # policy violation
        return
    try:
        # rate_limit()'s dependency only reads .headers / .client — a
        # WebSocket exposes the same shape as Request, so it works unchanged
        # here despite being written for HTTP routes.
        if not session_manager.session_exists(sid):
            await _new_session_rate_limit(ws)
        await _ensure_session(sid)
    except HTTPException:
        await ws.close(code=1008)  # too many new sessions from this IP
        return
    except session_manager.CapacityExceeded:
        await ws.close(code=1013)  # try again later
        return
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
