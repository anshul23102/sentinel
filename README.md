<div align="center">

# Sentinel
### API Failure Detection Platform

**Detects silent API failures, latency spikes, and cascading outages before your users do.**
Then explains exactly what broke, why, and how to fix it.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![Groq](https://img.shields.io/badge/Groq-Llama_3.3_70B-F55036?style=flat-square)](https://groq.com)
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

> **AI Assistant** - Streaming chat powered by Llama 3.3 70B

<img width="1449" height="734" alt="Screenshot 2026-05-25 at 9 54 55 PM" src="https://github.com/user-attachments/assets/133e8f6c-eabc-4e86-9e84-65d2fa89b70f" />

---

## How It Works

```
API Traffic (30 rps)
      |
      v
 Log Generator --> SQLite (WAL mode + indexes)
      |
      v
Anomaly Detector (Z-score, 60s sliding window per endpoint)
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
- **Llama 3.3 70B via Groq** analyzes every anomaly the moment it is detected
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
| **Backend** | Python 3.11, FastAPI, aiosqlite, WebSockets, SSE |
| **AI** | Groq Cloud, Llama 3.3 70B Versatile |
| **Detection** | Z-score, sliding window, least-squares linear regression |
| **Frontend** | React 18, Vite, Recharts, Canvas API |
| **Database** | SQLite with WAL mode, indexed for concurrent reads/writes |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Free Groq API key at [console.groq.com](https://console.groq.com)

### 1. Clone
```bash
git clone https://github.com/anshul23102/sentinel.git
cd sentinel
```

### 2. Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Add your GROQ_API_KEY to .env
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
|   +-- db.py                # SQLite with WAL mode, indexes, auto-pruning
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
```

---

## Team

| Name | Institute |
|---|---|
| Anshul Jain | Indraprastha Institute of Information Technology, Delhi |

---

<div align="center">

</div>
