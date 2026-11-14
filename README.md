<div align="center">

# Sentinel
### API Failure Detection Platform

**Detects silent API failures, latency spikes, and cascading outages, then explains what broke and why.**

[![CI](https://github.com/anshul23102/sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/anshul23102/sentinel/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![Groq](https://img.shields.io/badge/Groq-GPT--OSS_120B-F55036?style=flat-square)](https://groq.com)
[![License](https://img.shields.io/badge/License-MIT-a78bfa?style=flat-square)](LICENSE)

</div>

---

## The Problem

Modern APIs fail quietly. A database connection pool exhausts itself at 2 AM. A network partition splits an inventory service. A memory leak slowly degrades search for 40 minutes before anyone notices. By the time a user reports it, the damage is done.

Sentinel watches every endpoint continuously, decides statistically when behavior has stopped being normal, and produces an evidence-backed explanation of what changed.

---

## Two Ways to Use It

Sentinel has one detection engine and two data sources.

| Data source | What it is | Session ids |
|---|---|---|
| **Built-in simulator** | A traffic generator for a fictional e-commerce backend (8 endpoints, 5 injectable failure scenarios). This is what the public demo runs, so anyone can break something and watch it get caught. | Any id (the browser generates a UUID) |
| **Real ingestion** (`POST /api/ingest`) | Your own service posts its request logs and they go through the same detector, storage, and dashboard. No synthetic traffic is ever mixed in. | Must start with `live-` |

See [Monitoring Your Own API](#monitoring-your-own-api) for the second one.

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
 Simulator (30 rps)  or  POST /api/ingest (your real logs)
                 |
                 v
        PostgreSQL: every log row, every anomaly (durable history)
                 |
                 v
   Detector, per endpoint, per session:
     60 second sliding windows in Redis (time based, not count based)
     robust z-score, Isolation Forest, CUSUM, binomial error test,
     Holt forecast, Holt-Winters seasonal baseline
                 |
        anomaly raised? ---> evidence chain ---> GPT-OSS 120B analysis (Groq)
                 |
                 v
   WebSocket broadcast  --->  React dashboard (per-session, real time)
```

Every piece of state, in Postgres, in Redis, and in the WebSocket fan-out, is scoped to a session id. Two visitors on the same server never see each other's data, scenarios, or alerts.

---

## Detection Methods

No single statistic catches every kind of failure, so the detector layers several, each chosen for a different failure shape.

| Method | Catches | Why this one |
|---|---|---|
| **Robust z-score** (median and MAD, cutoff 3.5, Iglewicz and Hoaglin 1993) | A single tick whose average latency is far outside the endpoint's normal range | A mean and standard deviation baseline is dragged toward the very outliers it is trying to detect. Median and MAD are not. |
| **Isolation Forest** (scikit-learn) on `[avg latency, error rate, request count]` | Correlated deviations, where latency and errors are both mildly off together | Each metric alone can look unremarkable; the joint pattern does not. |
| **CUSUM** (Page, 1954) on per-tick averages | A persistent shift to a new regime, including a slow climb that never crosses the z-score threshold in any one tick | Structurally different from a point detector. Its threshold (10) was chosen by simulation: 0% false positives on 200 noise trials and 100% detection of a real shift, where the textbook value of 5 gave 9.5% false positives. |
| **One-proportion z-test** | Error surges, with the evidence expressed as standard errors above the endpoint's own baseline error rate | Error rate is a proportion, so the correct yardstick is the binomial standard error, not a z-score of status code numbers. |
| **Absolute error-rate floor** (15% by default) | Error surges, regardless of what the windows look like | A self-referential window can adapt to a sustained failure; a fixed floor cannot. |
| **Holt linear smoothing** | Short-horizon forecast ("where is latency heading in 5 seconds") | Down-weights old points, so it reacts to a slope change faster than ordinary least squares. |
| **Holt-Winters** (statsmodels) | Behavior that is abnormal for this point in the daily and weekly traffic cycle | Needs two full seasonal cycles of history and reports nothing until it has them. |
| **Cross-endpoint correlation** | Cascade failures: 2 or more endpoints critical at once points to a shared dependency | Cheap and explainable. |
| **SLO error budget and burn rate** | How fast the allowed failures are being spent, per endpoint (99% target by default) | The standard SRE way to say how urgent a failure is. |

Two design rules run through all of it:

- **A value is never scored against a baseline that already contains it.** The baseline is read before the new batch is added. An earlier version of this detector did the opposite and measurably under-reported real spikes; a test pins the fix.
- **When there is not enough data, say so.** Every statistic returns "no claim" below its minimum sample size instead of inventing a number.

Seasonality runs on a compressed clock (a simulated day is 3 real minutes) so it can be watched and tested within one sitting.

---

## Monitoring Your Own API

Send request logs to `POST /api/ingest`. Use a session id that starts with `live-`, which guarantees no synthetic traffic is generated for it.

```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -H "X-Session-Id: live-myapp" \
  -d '{"logs": [
        {"endpoint": "/api/checkout", "method": "POST", "status_code": 200, "latency_ms": 84.2},
        {"endpoint": "/api/checkout", "method": "POST", "status_code": 503, "latency_ms": 912.0}
      ]}'
```

The response reports how many records were accepted and any anomalies they raised. To watch it live, open `http://localhost:5173/?session=live-myapp`.

Rules, all enforced server side:

- Fields per record: `endpoint` (required, a path such as `/api/users/{id}`), `status_code` (100 to 599, required), `latency_ms` (0 to 600000, required), and optionally `method`, `service`, `error_message`.
- Send **route templates**, not raw URLs. Every distinct endpoint becomes its own set of windows and models, so a session may track at most 100 endpoints, and one request may contain at most 50 distinct ones.
- At most 500 records and 256 KB per request, enforced on the bytes actually received (so chunked uploads cannot bypass it).
- Timestamps are **always assigned by the server**. A client-supplied timestamp is ignored, because accepting one would let a caller write into the past of the time-windowed baselines.
- Rate limited to 60 requests per minute per client IP. With `REQUIRE_API_KEY=true`, an `X-API-Key` header is also required.
- Detection works best when you send roughly one batch per second, since each batch is scored against the history before it.

---

## Failure Simulation

| Scenario | What happens |
|---|---|
| **DB Slowdown** | Connection pool exhaustion; checkout, orders and cart slow to about 850 ms with 15% errors |
| **Memory Leak** | Heap pressure builds over roughly 45 seconds; search and products degrade progressively |
| **Rate Limit Cascade** | Auth 429s ripple through the login-dependent endpoints |
| **Network Partition** | Inventory unreachable; 65% of the affected requests fail |
| **Normal** | Healthy baseline, about 72 ms latency and under 1% errors |

---

## Dashboard

- Overview with live KPIs, charts, a service dependency graph, and a 40-snapshot health heatmap
- Endpoints page with per-endpoint latency, P95, error rate, uptime, **error budget remaining and burn rate**
- Incidents page with the evidence chain behind every alert, AI diagnosis, and CSV or JSON export
- Streaming AI assistant that is given the live system state
- A client-side trend estimate on the Overview page (least-squares slope over the last 10 seconds) that warns when latency is heading toward its SLA
- If no backend is reachable, the UI switches to a clearly labeled **Demo** mode that runs on local mock data in the same shapes the real API returns

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11, FastAPI, asyncpg, redis-py (asyncio), WebSockets, Server-Sent Events |
| **AI** | Groq Cloud, GPT-OSS 120B, async client |
| **Detection** | NumPy, scikit-learn (Isolation Forest), statsmodels (Holt, Holt-Winters) |
| **Frontend** | React 18, Vite, Recharts, Canvas API |
| **Storage** | PostgreSQL for durable logs and anomalies, Redis for hot sliding-window state and scenario control |
| **Delivery** | Docker Compose, GitHub Actions, CodeQL, Dependabot, config for Vercel (frontend) and Railway (backend) |

---

## Quick Start

### Prerequisites
- Python 3.11
- Node.js 18 or newer
- PostgreSQL and Redis running locally (`brew install postgresql@16 redis`, then `brew services start postgresql@16 redis`)
- Optional: a free Groq API key from [console.groq.com](https://console.groq.com) for AI analysis

### 1. Clone
```bash
git clone https://github.com/anshul23102/sentinel.git
cd sentinel
```

### 2. Backend
```bash
createdb sentinel   # one time; the tables are created automatically on first run
cd backend
pip install -r requirements.txt
cp .env.example .env
# add GROQ_API_KEY to .env; DATABASE_URL and REDIS_URL default to localhost
python3 -m uvicorn main:app --port 8000 --host 0.0.0.0 --forwarded-allow-ips=""
```

The `--forwarded-allow-ips=""` flag matters. Uvicorn otherwise trusts `X-Forwarded-For` from loopback connections on its own, which would let a caller defeat the per-IP rate limits. See [SECURITY.md](SECURITY.md).

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### Docker

The compose file starts Postgres, Redis, the backend, and the frontend together.

```bash
GROQ_API_KEY=your_groq_api_key_here docker compose up --build
```

The key is optional. Without it everything works except AI analysis.

- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000` (interactive API docs at `/docs`)

The database credentials in `docker-compose.yml` are for local development only. CI builds this stack and smoke tests it on every push (readiness, the frontend, and a real ingest round trip).

---

## Configuration

Set these in `backend/.env`. Every detection threshold is validated at startup; an invalid value stops the server with a clear message instead of silently misbehaving.

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | none | Enables AI analysis and chat |
| `DATABASE_URL` | `postgresql://localhost/sentinel` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `CORS_ORIGINS` | local dev origins | Comma separated browser origins allowed to call the API. Never use `*`. |
| `ADMIN_API_KEY` | none | Bypasses rate limits when sent as `X-API-Key` |
| `REQUIRE_API_KEY` | off | Turns the guarded POST routes into a hard lockdown that needs `ADMIN_API_KEY` |
| `TRUST_PROXY_HEADERS` | off | Only enable behind a reverse proxy that overwrites `X-Forwarded-For` |
| `MAX_SESSIONS` | `500` | Ceiling on concurrent sessions |
| `SENTINEL_LOG_RPS` | `30` | Simulator requests per second per session; `0` disables the simulator |
| `SENTINEL_SLO_TARGET` | `0.99` | Success-ratio target behind error budget and burn rate |
| `SENTINEL_ANOMALY_ZSCORE_THRESHOLD` | `3.5` | Robust z-score that flags a latency spike |
| `SENTINEL_ANOMALY_ZSCORE_CLEAR_THRESHOLD` | `1.5` | Robust z-score below which a latency alert clears |
| `SENTINEL_ANOMALY_ERROR_RATE_THRESHOLD` | `0.15` | Error-rate fraction that flags an error surge |
| `SENTINEL_ANOMALY_ERROR_RATE_CLEAR_THRESHOLD` | `0.05` | Error-rate fraction below which an error alert clears |
| `SENTINEL_ANOMALY_LATENCY_THRESHOLD_MS` | `250` | Minimum average latency to count as a latency spike |

---

## API

All routes are session scoped through the `X-Session-Id` header (letters, digits, `_` and `-`, up to 128 characters). A request with no header gets a fresh anonymous session.

| Route | Purpose | Limit per IP |
|---|---|---|
| `GET /healthz` | Liveness probe, no session created | none |
| `GET /readyz` | Readiness probe, checks Postgres and Redis, 503 when either is down | none |
| `GET /api/health` | Per-endpoint health, SLO fields, and monitoring status | 120 per minute |
| `GET /api/logs`, `/api/anomalies`, `/api/stats`, `/api/timeseries`, `/api/scenario` | Read data | 60 per minute |
| `GET /api/incidents/export` | CSV or JSON export of anomalies | 10 per minute |
| `POST /api/ingest` | Send real request logs | 60 per minute |
| `POST /api/scenario` | Switch the simulator scenario (refused for `live-` sessions) | 20 per minute |
| `POST /api/chat`, `/api/chat/stream` | AI assistant, plain or streamed | 10 per minute |
| `POST /api/incident-report` | Generate a structured incident report | 5 per minute |
| `WS /ws?session=ID` | Real-time feed | new-session limit |

Creating a brand-new session is limited to 10 per minute per IP, on top of the process-wide `MAX_SESSIONS` ceiling.

---

## Security

Sentinel is a public, multi-tenant demo, so the defaults are built around abuse resistance. Highlights, with the full threat model in [SECURITY.md](SECURITY.md):

- Per-IP rate limits on every route, a per-IP limit on creating sessions, and a hard session ceiling
- Proxy headers are not trusted unless explicitly enabled, and uvicorn's own proxy trust is disabled at every launch path
- Session ids are validated for shape and length before they touch Redis or Postgres
- All SQL is parameterized; the markdown renderer builds React elements and never uses `dangerouslySetInnerHTML`
- Constant-time API key comparison
- Heuristic prompt-injection guard on the chat endpoint (defense in depth, not a guarantee)
- Ingestion is hardened separately: strict schema, byte-counted body cap, endpoint-cardinality caps, server-assigned timestamps
- Dependency and code scanning: pinned CI actions, Dependabot, CodeQL, and a clean `pip-audit`

---

## Background Task Supervision

Each session runs a `log_pipeline` (simulator sessions only) and a `periodic_scan` task, managed by a `TaskSupervisor` that restarts a crashed task with exponential backoff (1s, 2s, 4s, up to 60s, with jitter) and cancels everything cleanly on shutdown. Idle sessions with no open connection are reaped after 5 minutes, which also stops their tasks and deletes their rows.

`/api/health` includes a `_monitoring` block showing whether each task is running and when the last scan completed.

---

## Testing

```bash
createdb sentinel_test   # one time; a separate database, never the demo's data
cd backend
pip install -r requirements-dev.txt
pytest
```

Tests run against a real Postgres (`sentinel_test`) and a real Redis (logical database 1) with no database mocks, because a mocked test passing while the real system broke is exactly the failure this avoids. `GROQ_API_KEY` is forced empty in tests, so the suite never calls an external service.

What is covered:

- The detection math against synthetic ground truth with hand-computed expected values (robust z-score, Isolation Forest, CUSUM, Holt, Holt-Winters, the proportion test, SLO accounting)
- Regression tests pinned to real bugs found during development (baseline pollution, count-based windows, a miscalibrated CUSUM threshold, zero-variance baselines)
- Session isolation between simultaneous visitors, and the rate limit, session cap, and proxy-trust behavior
- The ingest endpoint: validation, size caps, endpoint caps, end-to-end detection, API key lockdown
- The task supervisor's restart, backoff, and cancellation behavior

CI runs three jobs on every push and pull request: backend (ruff and pytest against service containers), frontend (production build), and a Docker job that builds the whole compose stack and smoke tests it.

---

## Known Limitations

Stated plainly, because they shape how to read the results.

- **The demo data is synthetic.** The simulator is realistic but invented, and the default thresholds were tuned against it. For real traffic, expect to tune them (all are environment variables).
- **Windows are self-referential.** Over a 60 second window, a sustained failure eventually becomes the window's own normal, which blunts the z-score. That is why the absolute error-rate floor, CUSUM, and the seasonal model run alongside it.
- **Seasonality needs history.** The Holt-Winters baseline stays silent until it has two full simulated days (about 6 real minutes) for an endpoint.
- **Sessions are not authenticated.** A session id is an unguessable-by-default identifier, not a credential. Treat it like an unlisted URL.
- **Single process.** The session registry and WebSocket fan-out live in process memory. Scaling out means sticky routing or moving them to Redis pub/sub.
- **Fixed-window rate limiting** can admit up to roughly twice the limit across a window boundary.
- **Prompt-injection defenses are heuristic.**
- **AI analysis depends on an external API** and degrades to a plain "unavailable" message when no key is configured.

---

## Project Structure

```
sentinel/
+-- backend/
|   +-- main.py              # FastAPI app: routes, session identity, WebSocket manager, ingest, SSE chat
|   +-- anomaly_detector.py  # Layered detector, evidence chains, health snapshot, cascade scan
|   +-- seasonal.py          # Holt forecast, Holt-Winters baseline, CUSUM
|   +-- slo.py               # Error budget and burn rate (pure math)
|   +-- log_generator.py     # Traffic simulator and the 5 failure scenarios
|   +-- state.py             # Redis: time-windowed sliding windows, feature rows, scenario state
|   +-- db.py                # PostgreSQL via asyncpg: logs, anomalies, seasonal buckets, pruning
|   +-- ai_agent.py          # Groq integration: analysis, streaming chat, incident reports
|   +-- prompt_guard.py      # Heuristic prompt-injection detection and input wrapping
|   +-- ratelimit.py         # Redis fixed-window limiter, API key gate, proxy-trust logic
|   +-- session_manager.py   # Session lifecycle, idle reaping, session ceiling
|   +-- task_supervisor.py   # Background task supervision with restart and backoff
|   +-- config.py            # Validated, environment-driven thresholds
|   +-- tests/               # pytest suite against real Postgres and Redis
+-- frontend/
|   +-- src/
|       +-- pages/           # Overview, Endpoints, Incidents, Assistant
|       +-- components/      # Charts, service graph, heatmap, toasts, markdown renderer
|       +-- hooks/           # useWebSocket (live feed, session id, demo fallback), mockData
+-- docker-compose.yml       # Postgres, Redis, backend, frontend
+-- .github/workflows/       # CI (backend, frontend, docker smoke test) and CodeQL
+-- SECURITY.md
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Sentinel is part of the Elite Coders Summer of Code 2026 program. Security issues should be reported privately; see [SECURITY.md](SECURITY.md).

---

## Team

| Name | Institute | Team |
|---|---|---|
| Anshul Jain | Indraprastha Institute of Information Technology, Delhi | BLOODWYRM |

Contributors are listed on the [contributors graph](https://github.com/anshul23102/sentinel/graphs/contributors).

---

<div align="center">

Built for **Elite Coders Open Source Hackathon 2026**

</div>
