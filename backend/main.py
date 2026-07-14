import asyncio
import csv
import io
import json
import os
from contextlib import asynccontextmanager
from typing import Optional

import aiosqlite
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from db import init_db, get_recent_logs, get_recent_anomalies, get_endpoint_stats, get_timeseries, insert_anomaly, prune_old_logs, DB_PATH  # noqa: E402
from log_generator import run_generator, set_scenario, get_current_scenario, SCENARIOS  # noqa: E402
from anomaly_detector import process_log_batch, get_health_snapshot, run_anomaly_scan  # noqa: E402
from ai_agent import analyze_anomaly, chat, chat_stream, generate_incident_report  # noqa: E402

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()

# Background pipeline
async def log_pipeline():
    """Main pipeline: generate logs → detect anomalies → broadcast."""
    async def broadcast_and_detect(message: dict):
        if message["type"] == "logs":
            new_anomalies = process_log_batch(message["data"])
            for anomaly in new_anomalies:
                # Insert FIRST so anomaly has an ID before AI analysis references it
                anomaly_id     = await insert_anomaly(anomaly)
                anomaly["id"]  = anomaly_id
                await manager.broadcast({"type": "anomaly", "data": anomaly})
                # Non-blocking AI analysis — ID is already in anomaly dict
                task = asyncio.create_task(_async_ai_analysis(anomaly))
                task.add_done_callback(
                    lambda t: t.exception() and print(f"[AI] Analysis task failed: {t.exception()}")
                )
        await manager.broadcast(message)

    await run_generator(broadcast_and_detect, rps=30)

async def _async_ai_analysis(anomaly: dict):
    """Run AI root cause analysis in background and broadcast result."""
    try:
        recent_logs = await get_recent_logs(120, anomaly["endpoint"])
        result      = await analyze_anomaly(anomaly, recent_logs)
        await manager.broadcast({"type": "ai_analysis", "data": result})
    except Exception as e:
        print(f"[AI] Analysis failed for {anomaly.get('endpoint')}: {e}")

async def periodic_scan():
    """Every 5s: run anomaly scan, broadcast health, and prune old DB rows."""
    tick = 0
    while True:
        await asyncio.sleep(5)
        tick += 1
        await run_anomaly_scan(manager.broadcast)
        health = get_health_snapshot()
        await manager.broadcast({"type": "health", "data": health})
        # Prune logs older than 15 minutes every 60s to keep DB lean
        if tick % 12 == 0:
            await prune_old_logs(minutes=15)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    pipeline_task = asyncio.create_task(log_pipeline())
    scan_task = asyncio.create_task(periodic_scan())

    try:
        yield
    finally:
        pipeline_task.cancel()
        scan_task.cancel()

        await asyncio.gather(
            pipeline_task,
            scan_task,
            return_exceptions=True,
        )

app = FastAPI(title="Sentinel — API Intelligence Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST endpoints
@app.get("/api/health")
async def health():
    return get_health_snapshot()

@app.get("/api/logs")
async def logs(limit: int = 100, endpoint: Optional[str] = None):
    return await get_recent_logs(limit, endpoint)

@app.get("/api/anomalies")
async def anomalies(limit: int = 20):
    return await get_recent_anomalies(limit)

@app.get("/api/stats")
async def stats(minutes: int = 5):
    return await get_endpoint_stats(minutes)

@app.get("/api/timeseries")
async def timeseries(minutes: int = 10):
    return await get_timeseries(minutes)

@app.get("/api/scenario")
async def get_scenario():
    return {"current": get_current_scenario(), "available": list(SCENARIOS.keys())}

class ScenarioRequest(BaseModel):
    scenario: str
    intensity: float = 1.0

@app.post("/api/scenario")
async def inject_scenario(req: ScenarioRequest):
    if req.scenario not in SCENARIOS:
        raise HTTPException(400, f"Unknown scenario. Valid: {list(SCENARIOS.keys())}")
    set_scenario(req.scenario, req.intensity)
    await manager.broadcast({
        "type": "scenario_change",
        "data": {
            "scenario":    req.scenario,
            "description": SCENARIOS[req.scenario]["description"],
            "intensity":   req.intensity,
        }
    })
    return {"status": "ok", "scenario": req.scenario}

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    response = await chat(req.message, req.history)
    return {"response": response}

@app.post("/api/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    """Server-Sent Events streaming chat — tokens arrive as they're generated."""
    async def event_generator():
        try:
            async for chunk in chat_stream(req.message, req.history):
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

@app.post("/api/incident-report")
async def incident_report():
    anomalies_data = await get_recent_anomalies(20)
    if not anomalies_data:
        return {"report": "No anomalies detected in the current monitoring window."}
    report = await generate_incident_report(anomalies_data, 10)
    return {"report": report}

@app.get("/api/incidents/export")
async def export_incidents(format: str = "csv"):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM anomalies ORDER BY detected_at DESC"
        )
        rows = await cursor.fetchall()

    incidents = [dict(row) for row in rows]

    if format.lower() == "json":
        content = json.dumps(incidents, indent=2, default=str)
        return StreamingResponse(
            io.StringIO(content),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=sentinel_incidents.json"},
        )

    output = io.StringIO()
    if incidents:
        writer = csv.DictWriter(output, fieldnames=incidents[0].keys())
        writer.writeheader()
        writer.writerows(incidents)
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
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    # Push current state immediately on connect
    health          = get_health_snapshot()
    recent_anomalies = await get_recent_anomalies(10)
    await ws.send_json({"type": "health",          "data": health})
    await ws.send_json({"type": "init_anomalies",  "data": recent_anomalies})
    await ws.send_json({"type": "scenario_change", "data": {"scenario": get_current_scenario()}})
    try:
        while True:
            try:
                await ws.receive_text()  # keep-alive / ping
            except Exception:
                pass  # ignore malformed frames — only WebSocketDisconnect exits the loop
    except WebSocketDisconnect:
        manager.disconnect(ws)
