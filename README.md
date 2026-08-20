<div align="center">

# Sentinel
### API Failure Detection Platform

**Detects silent API failures, latency spikes, and cascading outages before your users do.**
Then explains exactly what broke, why, and how to fix it.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![Groq](https://img.shields.io/badge/Groq-GPT--OSS_120B-F55036?style=flat-square)](https://groq.com)
[![License](https://img.shields.io/badge/License-MIT-a78bfa?style=flat-square)](LICENSE)

</div>

---

## The Problem

Modern APIs fail in silence. A database connection pool exhausts itself at 2 AM. A network partition splits your inventory service. A memory leak slowly degrades search for 40 minutes before anyone notices. By the time a user reports it, thousands in revenue are already gone.

**Sentinel watches every endpoint, every second. When something breaks, it tells you exactly why.**

---

## Screenshots

> **Overview** - Live KPI dashboard with health score and scenario simulator

<img width="1452" height="743" alt="Screenshot 2026-05-25 at 9 53 54 PM" src="https://github.com/user-attachments/assets/3b655921-6c49-4bcf-8e29-d6541c6aafcc" />

&nbsp;

> **Incidents** - Root cause chain with cascade failure visualization

<img width="1445" height="742" alt="Screenshot 2026-05-25 at 9 54 46 PM" src="https://github.com/user-attachments/assets/772c5e32-6b4b-476c-bdcd-f1849e54874d" />

&nbsp;

> **Service Dependency Graph** - Real-time particle flow showing live traffic between microservices

<img width="1455" height="748" alt="Screenshot 2026-05-25 at 9 54 22 PM" src="https://github.com/user-attachments/assets/27a5e128-23c0-4aae-9ae3-cd7a9b73be2d" />

&nbsp;

> **AI Assistant** - Streaming chat powered by GPT-OSS 120B

<img width="1449" height="734" alt="Screenshot 2026-05-25 at 9 54 55 PM" src="https://github.com/user-attachments/assets/133e8f6c-eabc-4e86-9e84-65d2fa89b70f" />

---

## How It Works

```
API Traffic (30 rps)
      |
      v
 Log Generator --> PostgreSQL (durable log/anomaly history)
      |
      v
Anomaly Detector (Z-score, 60s sliding window per endpoint, state in Redis)
      |
      +-- Anomaly detected? --> Groq AI Analysis --> Root Cause Chain
      |
      v
WebSocket Broadcast --> React Dashboard (real-time)
      |
      +-- Live KPIs  (latency, error rate, rps)
      +-- Service Dependency Graph  (canvas particles)
      +-- Health Heatmap  (40 historical snapshots)
      +-- Toast Notifications  (critical alerts)
      +-- AI Chat  (SSE token streaming)
```

---

## Features

### Real-Time Detection
- **Z-score anomaly detection** on 60-second sliding windows per endpoint
- Catches latency spikes, error surges, and cascade failures automatically
- Health scoring system (0 to 100) across all 8 monitored services
- Sub-second WebSocket broadcasting to all connected clients

### AI Root Cause Analysis
- **GPT-OSS 120B via Groq** analyzes every anomaly the moment it is detected
- Produces a root cause chain with confidence scores: `Auth failing -> Cart errors -> Checkout down`
- Streaming AI chat: ask anything about your system in plain English
- One-click structured incident report generation

### Service Dependency Graph
- Canvas-based real-time visualization of all 8 microservices
- Particle flows show active request traffic between services
- Node colors reflect live health status (green / yellow / red)
- Cascade failures visually propagate through the dependency graph

### Failure Simulation
| Scenario | What Happens |
|---|---|
| **DB Slowdown** | Connection pool exhaustion, checkout cascade timeout at 850ms avg |
| **Memory Leak** | Heap pressure builds over 90s, search and products slowly degrade |
| **Rate Limit Cascade** | Auth 429s ripple through all login-dependent services |
| **Network Partition** | Inventory unreachable, 65% of checkouts fail with ECONNREFUSED |
| **Normal** | Healthy baseline ~80ms latency, less than 1% error rate |

### Dashboard
- Tilt-responsive KPI cards with flash animations on metric changes
- Predictive insights using linear regression that flag SLA breaches before they happen
- Health heatmap: 40 snapshots x 8 endpoints = full history at a glance
- Live log stream with color-coded status codes, latency, and method

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11, FastAPI, asyncpg, redis-py, WebSockets, SSE |
| **AI** | Groq Cloud, GPT-OSS 120B |
| **Detection** | Z-score, sliding window, least-squares linear regression |
| **Frontend** | React 18, Vite, Recharts, Canvas API |
| **Database** | PostgreSQL for durable logs/anomalies; Redis for hot sliding-window state and scenario control — both survive a backend restart |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL and Redis running locally (`brew install postgresql@16 redis`, then `brew services start postgresql@16 redis`)
- Free Groq API key at [console.groq.com](https://console.groq.com)

### 1. Clone
```bash
git clone https://github.com/anshul23102/sentinel-api-intelligence.git
cd sentinel-api-intelligence
```

### 2. Backend
```bash
createdb sentinel   # one-time, tables are created automatically on first run
cd backend
pip install -r requirements.txt
cp .env.example .env
# Add your GROQ_API_KEY to .env — DATABASE_URL and REDIS_URL default to localhost
python3 -m uvicorn main:app --port 8000 --host 0.0.0.0
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`

---

## Project Structure

```
sentinel-api-intelligence/
+-- backend/
|   +-- main.py              # FastAPI app, WebSocket manager, SSE streaming
|   +-- anomaly_detector.py  # Z-score detection, health snapshot, scoring
|   +-- log_generator.py     # Synthetic traffic at 30 rps, 5 failure scenarios
|   +-- ai_agent.py          # Groq integration, streaming chat, root cause analysis
|   +-- db.py                # PostgreSQL logs/anomalies via asyncpg, auto-pruning
|   +-- state.py             # Redis-backed sliding windows, active anomalies, scenario state
|   +-- requirements.txt
+-- frontend/
    +-- src/
        +-- pages/
        |   +-- Overview.jsx      # KPIs, live charts, service graph, heatmap
        |   +-- Endpoints.jsx     # Per-endpoint stats and SLA tracking
        |   +-- Incidents.jsx     # Anomaly feed with root cause chains
        |   +-- Assistant.jsx     # Streaming AI chat interface
        +-- components/
        |   +-- ServiceGraph.jsx  # Canvas dependency graph with particles
        |   +-- HealthHeatmap.jsx # 8x40 status grid with hover tooltips
        |   +-- LiveChart.jsx     # Recharts area charts with SLA reference lines
        |   +-- ToastNotifications.jsx
        |   +-- SparkField.jsx    # Background particle constellation
        +-- hooks/
            +-- useWebSocket.js   # WS state, timeseries merging, scenario control
```

---

## Environment Variables

**Backend** (`backend/.env`):
```
GROQ_API_KEY=your_groq_api_key_here
DATABASE_URL=postgresql://localhost/sentinel
REDIS_URL=redis://localhost:6379/0
ADMIN_API_KEY=            # optional — bypasses rate limiting for X-API-Key requests
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

---

## Rate Limiting & CORS

The `/api/chat`, `/api/chat/stream`, `/api/scenario`, and `/api/incident-report` endpoints are rate-limited per client IP using a fixed-window counter in Redis (10/min for chat, 20/min for scenario changes, 5/min for incident reports) — these are the only endpoints that either cost Groq API tokens or can disrupt what other simultaneous visitors see. Everything else (health, logs, anomalies, stats, timeseries, the WebSocket feed) stays open and unlimited, since the whole point of this project is a live public demo anyone can watch and try.

`CORS_ORIGINS` restricts which browser origins may call the API — set this to your deployed frontend URL in production rather than using `*`.

---

## Testing

```bash
createdb sentinel_test   # one-time — a separate database, never the demo's live data
cd backend
pip install -r requirements-dev.txt
pytest
```

Tests run against a real Postgres (`sentinel_test`) and a real Redis (logical DB 1, separate from the app's DB 0) — no mocks for the database layer, since that's exactly the kind of gap that let a mocked test pass while the real system broke. `GROQ_API_KEY` is forced empty in tests, so the suite never makes a real external API call or spends real quota; the "AI unavailable" degradation path is itself part of what gets tested.

Coverage: pure-math unit tests for the detection algorithms (robust z-score, Isolation Forest, Holt-Winters, CUSUM, Holt linear forecast) against known synthetic ground truth; integration tests for session-scoped Postgres/Redis state; API-level tests against the real FastAPI app, including session isolation between two simultaneous "visitors" and rate-limit enforcement. Several tests exist specifically to pin real findings from development — a CUSUM threshold miscalibration, an MAD-based z-score's degenerate zero-variance case, a median/MAD ~50% breakdown-point limitation on self-referential sliding windows — so a future change can't silently regress them.

---

## Team

| Name | Institute |
|---|---|
| Anshul Jain | Indraprastha Institute of Information Technology, Delhi |

---

<div align="center">

Built for **CodeStorm 2026**

</div>
