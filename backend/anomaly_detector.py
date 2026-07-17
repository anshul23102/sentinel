import numpy as np
from collections import defaultdict, deque
from datetime import datetime, timezone
from db import insert_anomaly

# Sliding windows per endpoint (60 seconds of data)
_latency_windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=60))
_error_windows:   dict[str, deque] = defaultdict(lambda: deque(maxlen=60))
_request_windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=60))

# Track already-firing anomalies to avoid spam
_active_anomalies: dict[str, dict] = {}

# Thresholds
LATENCY_Z_THRESHOLD  = 2.5
ERROR_RATE_THRESHOLD = 0.15   # 15% of requests returning 4xx or 5xx
PREDICTION_WINDOW    = 5       # seconds ahead to project
PREDICTION_LOOKBACK  = 20      # recent seconds for trend line

def _z_score(value: float, window: deque) -> float:
    if len(window) < 10:
        return 0.0
    arr = np.array(window)
    std = arr.std()
    if std == 0:
        # If baseline has zero variance, any value above the mean is a significant spike
        return 3.0 if value > arr.mean() else 0.0
    return (value - arr.mean()) / std

def _error_rate(window: deque) -> float:
    """Count ANY failed request (4xx + 5xx) — aligns with frontend liveStats."""
    if not window:
        return 0.0
    return sum(1 for x in window if x >= 400) / len(window)

def _predict_trend(window: deque, steps_ahead: int = 5) -> float:
    """Linear regression to predict value N steps ahead."""
    if len(window) < 5:
        return list(window)[-1] if window else 0.0
    y = np.array(list(window)[-PREDICTION_LOOKBACK:])
    x = np.arange(len(y))
    coeffs = np.polyfit(x, y, 1)
    return float(coeffs[0] * (len(y) + steps_ahead) + coeffs[1])

def _dynamic_confidence(window: deque, base: float) -> float:
    """Scale confidence with sample size — more data = higher confidence."""
    scale = min(1.0, len(window) / 40.0)
    return round(base * 0.6 + base * 0.4 * scale, 2)

def process_log_batch(logs: list[dict]) -> list[dict]:
    """Update windows with new logs, return any new anomalies detected."""
    endpoint_batches: dict[str, list] = defaultdict(list)
    for log in logs:
        ep = log["endpoint"]
        endpoint_batches[ep].append(log)

    new_anomalies = []

    for endpoint, batch in endpoint_batches.items():
        # FIX 2: Append error and request logs immediately so they are counted in the current check
        for log in batch:
            _error_windows[endpoint].append(log["status_code"])
            _request_windows[endpoint].append(1)

        avg_latency = np.mean([log["latency_ms"] for log in batch])
        # Calculate z-score BEFORE updating latency window to prevent baseline data pollution
        z           = _z_score(avg_latency, _latency_windows[endpoint])
        err_rate    = _error_rate(_error_windows[endpoint])

        anomalies_for_ep = []

        # Latency spike detection
        if z > LATENCY_Z_THRESHOLD and avg_latency > 250:
            key = f"latency_{endpoint}"
            if key not in _active_anomalies:
                predicted_latency = _predict_trend(_latency_windows[endpoint], PREDICTION_WINDOW)
                severity = "critical" if z > 3.5 or avg_latency > 800 else "warning"
                anomaly = {
                    "detected_at":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                    "anomaly_type":    "latency_spike",
                    "severity":        severity,
                    "endpoint":        endpoint,
                    "description":     f"Latency spike: avg {avg_latency:.0f}ms (z={z:.1f}σ). Predicted {predicted_latency:.0f}ms in {PREDICTION_WINDOW}s.",
                    "root_cause_chain": _build_root_cause_chain(endpoint, "latency", avg_latency, err_rate),
                    "z_score":         round(z, 2),
                    "avg_latency":     round(avg_latency, 1),
                    "predicted_latency": round(predicted_latency, 1),
                }
                _active_anomalies[key] = anomaly
                anomalies_for_ep.append(anomaly)
        elif z < 1.5:  # FIX 1: Aligned outwardly so it can actually execute and clear old anomalies
            _active_anomalies.pop(f"latency_{endpoint}", None)

        # Error rate surge detection
        if err_rate > ERROR_RATE_THRESHOLD:
            key = f"errors_{endpoint}"
            if key not in _active_anomalies:
                predicted_err_rate = _predict_trend(
                    deque([1 if s >= 400 else 0 for s in _error_windows[endpoint]], maxlen=60),
                    PREDICTION_WINDOW
                )
                severity = "critical" if err_rate > 0.35 else "warning"
                anomaly = {
                    "detected_at":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                    "anomaly_type":    "error_surge",
                    "severity":        severity,
                    "endpoint":        endpoint,
                    "description":     f"Error surge: {err_rate*100:.1f}% failure rate (threshold {ERROR_RATE_THRESHOLD*100:.0f}%). Trend: {'rising' if predicted_err_rate > err_rate else 'stable'}.",
                    "root_cause_chain": _build_root_cause_chain(endpoint, "errors", avg_latency, err_rate),
                    "error_rate":       round(err_rate, 3),
                    "predicted_error_rate": round(max(0.0, predicted_err_rate), 3),
                }
                _active_anomalies[key] = anomaly
                anomalies_for_ep.append(anomaly)
        elif err_rate < 0.05:  # FIX 1: Aligned outwardly so it can clear resolved error surges
            _active_anomalies.pop(f"errors_{endpoint}", None)

        new_anomalies.extend(anomalies_for_ep)

        # Update sliding latency window after calculations to prevent baseline data pollution
        for log in batch:
            _latency_windows[endpoint].append(log["latency_ms"])
            _error_windows[endpoint].append(log["status_code"])
            _request_windows[endpoint].append(1)

    return new_anomalies

def _build_root_cause_chain(endpoint: str, anomaly_type: str, avg_latency: float, err_rate: float) -> list[dict]:
    """Build a heuristic root cause chain with dynamic confidence scores."""
    chain = []

    if anomaly_type == "latency" and avg_latency > 400:
        chain = [
            {"step": 1, "component": "Database", "signal": f"Query latency elevated ({avg_latency:.0f}ms avg — pool saturation likely)", "confidence": _dynamic_confidence(_latency_windows[endpoint], 0.87)},
            {"step": 2, "component": "Connection Pool", "signal": "Checkout queue depth rising — workers blocked on DB I/O", "confidence": _dynamic_confidence(_latency_windows[endpoint], 0.78)},
            {"step": 3, "component": endpoint, "signal": "Downstream timeout propagating to clients", "confidence": _dynamic_confidence(_latency_windows[endpoint], 0.93)},
        ]
    elif anomaly_type == "latency":
        chain = [
            {"step": 1, "component": "Application Layer", "signal": f"Response time elevated ({avg_latency:.0f}ms). GC pause or thread contention suspected.", "confidence": _dynamic_confidence(_latency_windows[endpoint], 0.72)},
            {"step": 2, "component": endpoint, "signal": "Requests completing slowly — no hard errors yet", "confidence": _dynamic_confidence(_latency_windows[endpoint], 0.85)},
        ]
    elif anomaly_type == "errors" and err_rate > 0.30:
        chain = [
            {"step": 1, "component": "Upstream Service", "signal": f"{err_rate*100:.0f}% of requests failing — dependency returning 4xx/5xx", "confidence": _dynamic_confidence(_error_windows[endpoint], 0.82)},
            {"step": 2, "component": "Circuit Breaker", "signal": "Failure threshold breached — circuit may trip open", "confidence": _dynamic_confidence(_error_windows[endpoint], 0.75)},
            {"step": 3, "component": endpoint, "signal": "Service unable to fulfil requests — cascading upstream", "confidence": _dynamic_confidence(_error_windows[endpoint], 0.95)},
        ]
    else:
        chain = [
            {"step": 1, "component": "Upstream Dependency", "signal": f"Intermittent errors ({err_rate*100:.1f}%). Retry logic may be masking failures.", "confidence": _dynamic_confidence(_error_windows[endpoint], 0.60)},
            {"step": 2, "component": endpoint, "signal": "Anomaly detected — AI analysis in progress", "confidence": _dynamic_confidence(_error_windows[endpoint], 0.50)},
        ]

    return chain

def get_health_snapshot() -> dict:
    """Current health of all monitored endpoints, with uptime percentage."""
    snapshot = {}
    for endpoint in _latency_windows:
        window  = _latency_windows[endpoint]
        err_win = _error_windows[endpoint]
        if not window:
            continue

        err_rate = _error_rate(err_win)
        avg_lat  = float(np.mean(window))

        status = "healthy"
        if err_rate > 0.28 or avg_lat > 600:
            status = "critical"
        elif err_rate > 0.08 or avg_lat > 200:
            status = "degraded"

        # Uptime = success requests / total requests
        total   = len(err_win)
        errors  = sum(1 for x in err_win if x >= 400)
        uptime  = round(((total - errors) / total) * 100, 1) if total > 0 else 100.0

        p95 = round(float(np.percentile(window, 95)), 1) if len(window) >= 5 else round(avg_lat, 1)

        snapshot[endpoint] = {
            "status":         status,
            "avg_latency_ms": round(avg_lat, 1),
            "p95_latency_ms": p95,
            "error_rate":     round(err_rate, 3),
            "uptime_pct":     uptime,
            "sample_size":    len(window),
        }
    return snapshot

async def run_anomaly_scan(broadcast_fn):
    """Periodic scan to catch cross-endpoint cascade failures."""
    snapshot         = get_health_snapshot()
    critical_endpoints = [ep for ep, s in snapshot.items() if s["status"] == "critical"]

    if len(critical_endpoints) >= 2:
        key = "multi_endpoint_cascade"
        if key not in _active_anomalies:
            affected_str = ", ".join(critical_endpoints[:3])
            anomaly = {
                "detected_at":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                "anomaly_type":    "cascade_failure",
                "severity":        "critical",
                "endpoint":        "multiple",
                "description":     f"Cascade failure across {len(critical_endpoints)} endpoints ({affected_str}{'...' if len(critical_endpoints)>3 else ''}). Shared infrastructure issue likely.",
                "root_cause_chain": [
                    {"step": 1, "component": "Shared Infrastructure", "signal": f"{len(critical_endpoints)} services degraded simultaneously — common dependency failing", "confidence": 0.91},
                    {"step": 2, "component": "Database / Cache Layer", "signal": "Correlated failures point to DB connection pool or Redis cluster", "confidence": 0.84},
                    {"step": 3, "component": "All Affected Endpoints", "signal": "Services failing due to shared dep — not individual service bugs", "confidence": 0.96},
                ],
                "affected_endpoints": critical_endpoints,
            }
            _active_anomalies[key] = anomaly
            anomaly_id = await insert_anomaly(anomaly)
            anomaly["id"] = anomaly_id
            await broadcast_fn({"type": "anomaly", "data": anomaly})
    elif "multi_endpoint_cascade" in _active_anomalies and len(critical_endpoints) < 2:
        del _active_anomalies["multi_endpoint_cascade"]
