import numpy as np
from collections import defaultdict
from datetime import datetime, timezone
from sklearn.ensemble import IsolationForest
from db import insert_anomaly, get_seasonal_history
from log_generator import BUCKETS_PER_DAY
from seasonal import holt_linear_forecast, fit_seasonal_baseline, cusum_changepoint
import state

# MAD_Z_THRESHOLD: 3.5 is the standard cutoff for the modified z-score
# (Iglewicz & Hoaglin, "How to Detect and Handle Outliers", 1993) — chosen
# specifically over the classic mean/std z-score because a robust median/MAD
# baseline doesn't get dragged off-center by the very anomalies it's trying
# to detect, whereas mean/std does.
MAD_Z_THRESHOLD        = 3.5
ERROR_RATE_THRESHOLD   = 0.15   # absolute floor — keeps quiet, low-traffic endpoints from false-alarming on noise
ISOLATION_MIN_SAMPLES  = 15     # need enough history before the multivariate model means anything
PREDICTION_WINDOW      = 5      # seconds ahead to project

def _robust_z_series(window: list[float]) -> np.ndarray:
    """Modified z-score for every point in the window, relative to the window's
    own median/MAD. Returns an array so callers can both read the latest value
    and compute an honest percentile-rank confidence from the rest."""
    arr = np.array(window, dtype=float)
    if len(arr) < 10:
        return np.zeros_like(arr)
    median = np.median(arr)
    mad = np.median(np.abs(arr - median))
    if mad == 0:
        # A perfectly uniform baseline (a quiet, very stable endpoint) makes
        # the standard MAD-normalized z-score mathematically undefined.
        # Going fully blind here would mean such an endpoint could never be
        # flagged again until its own noise floor returns — so fall back to
        # a small epsilon scaled to the data itself rather than zero out.
        mad = max(abs(median) * 0.01, 1e-6)
    return 0.6745 * (arr - median) / mad

def _percentile_confidence(z_series: np.ndarray) -> float:
    """How extreme is the latest point compared to the rest of this endpoint's
    own recent history? A real, explainable number — not a formula tuned to
    just converge toward a fixed constant as more samples arrive."""
    if len(z_series) < 10:
        return 0.0
    current = abs(z_series[-1])
    return round(float((np.abs(z_series[:-1]) < current).mean()), 2)

def _error_rate(window: list[float]) -> float:
    """Count ANY failed request (4xx + 5xx) — aligns with frontend liveStats."""
    if not window:
        return 0.0
    return sum(1 for x in window if x >= 400) / len(window)

def _multivariate_anomaly(feature_window: list[list[float]]) -> tuple[float, float]:
    """Fit an Isolation Forest on this endpoint's own recent
    [avg_latency, error_rate, req_count] history and score how anomalous the
    latest point is relative to its own peers. This is what catches a
    correlated anomaly — latency and error rate both mildly elevated at the
    same time — that no single-metric z-score can see, because each metric
    alone might still look unremarkable.
    Returns (raw_score, percentile_confidence)."""
    if len(feature_window) < ISOLATION_MIN_SAMPLES:
        return 0.0, 0.0
    X = np.array(feature_window)
    clf = IsolationForest(n_estimators=64, contamination=0.15, random_state=42)
    clf.fit(X)
    scores = -clf.decision_function(X)  # flip sign: higher = more anomalous
    latest = float(scores[-1])
    percentile = round(float((scores[:-1] < latest).mean()), 2) if len(scores) > 1 else 0.0
    return latest, percentile

async def process_log_batch(sid: str, logs: list[dict]) -> list[dict]:
    """Update this session's Redis-backed windows with new logs, return any
    new anomalies detected. Every piece of state here is scoped to `sid` —
    two sessions never see or influence each other's detector state."""
    endpoint_batches: dict[str, list] = defaultdict(list)
    for log in logs:
        endpoint_batches[log["endpoint"]].append(log)

    new_anomalies = []

    for endpoint, batch in endpoint_batches.items():
        lat_key = state.latency_key(sid, endpoint)
        err_key = state.error_key(sid, endpoint)

        for log in batch:
            await state.push_window(sid, lat_key, log["latency_ms"], endpoint)
            await state.push_window(sid, err_key, log["status_code"], endpoint)

        latency_window = await state.get_window(lat_key)
        error_window   = await state.get_window(err_key)

        avg_latency = float(np.mean([l["latency_ms"] for l in batch]))
        err_rate    = _error_rate(error_window)

        # Push this tick's aggregate into the multivariate feature window
        await state.push_feature_row(sid, endpoint, [avg_latency, err_rate, float(len(batch))])
        feature_window = await state.get_feature_window(sid, endpoint)
        mv_score, mv_confidence = _multivariate_anomaly(feature_window)

        lat_z_series = _robust_z_series(latency_window)
        err_z_series = _robust_z_series(error_window)
        lat_z = float(lat_z_series[-1]) if len(lat_z_series) else 0.0
        err_z = float(err_z_series[-1]) if len(err_z_series) else 0.0
        lat_confidence = _percentile_confidence(lat_z_series)
        err_confidence = _percentile_confidence(err_z_series)

        # CUSUM on the per-tick AGGREGATED latency series (not raw per-request
        # values — confirmed via testing that raw per-request CUSUM is
        # over-sensitive to a single naturally-slow request). Catches a
        # persistent regime shift, which is structurally different from a
        # point anomaly: a slow gradual climb that never crosses the z-score
        # threshold in any single tick can still trip CUSUM once it's
        # accumulated enough sustained deviation.
        agg_latency_series = [row[0] for row in feature_window]
        cusum_fired, cusum_mag = cusum_changepoint(agg_latency_series)

        # Seasonal (Holt-Winters) baseline — degrades honestly to None until
        # at least 2 full simulated days of this session's own bucket history exist.
        seasonal_history = await get_seasonal_history(sid, endpoint, limit=BUCKETS_PER_DAY * 14)
        seasonal_fit = fit_seasonal_baseline(seasonal_history, period=BUCKETS_PER_DAY)
        seasonal_z = 0.0
        if seasonal_fit and seasonal_fit["std"] > 0:
            seasonal_z = (avg_latency - seasonal_fit["expected"]) / seasonal_fit["std"]

        anomalies_for_ep = []

        # Latency spike detection — robust z-score, not mean/std
        if lat_z > MAD_Z_THRESHOLD and avg_latency > 250:
            key = f"latency_{endpoint}"
            if await state.get_active_anomaly(sid, key) is None:
                predicted_latency = holt_linear_forecast(latency_window, PREDICTION_WINDOW)
                severity = "critical" if lat_confidence > 0.9 or avg_latency > 800 else "warning"
                anomaly = {
                    "detected_at":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                    "anomaly_type":    "latency_spike",
                    "severity":        severity,
                    "endpoint":        endpoint,
                    "description":     f"Latency spike: avg {avg_latency:.0f}ms (robust z={lat_z:.1f}σ, more extreme than {lat_confidence*100:.0f}% of recent history). Holt forecast: {predicted_latency:.0f}ms in {PREDICTION_WINDOW}s.",
                    "root_cause_chain": _build_evidence_chain(endpoint, avg_latency, err_rate, lat_z, err_z, lat_confidence, err_confidence, mv_score, mv_confidence, seasonal_fit, seasonal_z, cusum_fired, cusum_mag),
                    "z_score":         round(lat_z, 2),
                    "avg_latency":     round(avg_latency, 1),
                    "predicted_latency": round(predicted_latency, 1),
                    "multivariate_score": round(mv_score, 3),
                }
                await state.set_active_anomaly(sid, key, anomaly)
                anomalies_for_ep.append(anomaly)
            elif lat_z < 1.5:
                await state.clear_active_anomaly(sid, key)

        # Error rate surge detection — absolute floor kept (this is what stops
        # a naturally-quiet endpoint from false-alarming on a single failed request)
        if err_rate > ERROR_RATE_THRESHOLD:
            key = f"errors_{endpoint}"
            if await state.get_active_anomaly(sid, key) is None:
                predicted_err_rate = holt_linear_forecast(
                    [1.0 if s >= 400 else 0.0 for s in error_window],
                    PREDICTION_WINDOW
                )
                severity = "critical" if err_rate > 0.35 else "warning"
                anomaly = {
                    "detected_at":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                    "anomaly_type":    "error_surge",
                    "severity":        severity,
                    "endpoint":        endpoint,
                    "description":     f"Error surge: {err_rate*100:.1f}% failure rate (threshold {ERROR_RATE_THRESHOLD*100:.0f}%). Trend: {'rising' if predicted_err_rate > err_rate else 'stable'}.",
                    "root_cause_chain": _build_evidence_chain(endpoint, avg_latency, err_rate, lat_z, err_z, lat_confidence, err_confidence, mv_score, mv_confidence, seasonal_fit, seasonal_z, cusum_fired, cusum_mag),
                    "error_rate":       round(err_rate, 3),
                    "predicted_error_rate": round(max(0.0, predicted_err_rate), 3),
                    "multivariate_score": round(mv_score, 3),
                }
                await state.set_active_anomaly(sid, key, anomaly)
                anomalies_for_ep.append(anomaly)
            elif err_rate < 0.05:
                await state.clear_active_anomaly(sid, key)

        # Changepoint detection — only raised when latency/error-surge didn't
        # already fire this tick, so a genuine step-change doesn't produce
        # two separate alerts for the same underlying event.
        cp_key = f"changepoint_{endpoint}"
        if cusum_fired and not anomalies_for_ep:
            if await state.get_active_anomaly(sid, cp_key) is None:
                anomaly = {
                    "detected_at":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                    "anomaly_type":    "changepoint",
                    "severity":        "critical" if cusum_mag > 15 else "warning",
                    "endpoint":        endpoint,
                    "description":     f"Sustained regime shift detected via CUSUM (magnitude {cusum_mag:.1f}σ, threshold 10σ) — behavior has persistently changed, not a single noisy tick.",
                    "root_cause_chain": _build_evidence_chain(endpoint, avg_latency, err_rate, lat_z, err_z, lat_confidence, err_confidence, mv_score, mv_confidence, seasonal_fit, seasonal_z, cusum_fired, cusum_mag),
                    "cusum_magnitude": cusum_mag,
                }
                await state.set_active_anomaly(sid, cp_key, anomaly)
                anomalies_for_ep.append(anomaly)
        elif not cusum_fired:
            await state.clear_active_anomaly(sid, cp_key)

        new_anomalies.extend(anomalies_for_ep)

    return new_anomalies

def _build_evidence_chain(endpoint: str, avg_latency: float, err_rate: float,
                           lat_z: float, err_z: float, lat_confidence: float,
                           err_confidence: float, mv_score: float, mv_confidence: float,
                           seasonal_fit: dict | None = None, seasonal_z: float = 0.0,
                           cusum_fired: bool = False, cusum_mag: float = 0.0) -> list[dict]:
    """Every entry here is a real computed deviation on this endpoint's own
    recent history — not a hardcoded infrastructure narrative. Ranks latency
    and error-rate deviations by how extreme they actually are, then reports
    the multivariate (combined-signal) score as the final, honest confidence
    that this is a genuine joint anomaly rather than one noisy metric."""
    signals = [
        ("Latency",    lat_z, lat_confidence, f"{avg_latency:.0f}ms avg, {lat_z:.1f} robust-σ from this endpoint's own recent baseline"),
        ("Error rate", err_z, err_confidence, f"{err_rate*100:.1f}% failing, {err_z:.1f} robust-σ from this endpoint's own recent baseline"),
    ]
    signals.sort(key=lambda s: abs(s[1]), reverse=True)

    chain = []
    for i, (name, z, confidence, detail) in enumerate(signals, start=1):
        if abs(z) < 1.0:
            continue  # not a meaningful contributor — don't manufacture a step for it
        chain.append({
            "step": i,
            "component": name,
            "signal": detail,
            "confidence": confidence,
        })

    if mv_confidence > 0:
        chain.append({
            "step": len(chain) + 1,
            "component": "Combined signal (Isolation Forest)",
            "signal": f"Joint latency+error+traffic pattern is more anomalous than {mv_confidence*100:.0f}% of this endpoint's own recent behavior (score {mv_score:.2f})",
            "confidence": mv_confidence,
        })

    if cusum_fired:
        chain.append({
            "step": len(chain) + 1,
            "component": "Sustained shift (CUSUM)",
            "signal": f"Behavior has persistently changed, not just this tick — cumulative deviation {cusum_mag:.1f}σ over the recent window",
            "confidence": round(min(0.99, cusum_mag / 20), 2),
        })

    if seasonal_fit is not None and abs(seasonal_z) > 1.0:
        chain.append({
            "step": len(chain) + 1,
            "component": "Seasonal baseline (Holt-Winters)",
            "signal": f"{avg_latency:.0f}ms vs {seasonal_fit['expected']:.0f}ms expected for this point in the daily/weekly traffic cycle ({seasonal_z:+.1f}σ from the seasonal model)",
            "confidence": round(min(0.99, abs(seasonal_z) / 6), 2),
        })

    if not chain:
        chain.append({
            "step": 1,
            "component": endpoint,
            "signal": "Threshold crossed but no single metric stands out strongly — likely a borderline or transient blip",
            "confidence": 0.3,
        })

    return chain

async def get_health_snapshot(sid: str) -> dict:
    """Current health of all endpoints this session has generated traffic
    for, with uptime percentage."""
    snapshot = {}
    for endpoint in await state.get_known_endpoints(sid):
        latency_window = await state.get_window(state.latency_key(sid, endpoint))
        error_window   = await state.get_window(state.error_key(sid, endpoint))
        if not latency_window:
            continue

        err_rate = _error_rate(error_window)
        avg_lat  = float(np.mean(latency_window))

        status = "healthy"
        if err_rate > 0.28 or avg_lat > 600:
            status = "critical"
        elif err_rate > 0.08 or avg_lat > 200:
            status = "degraded"

        # Uptime = success requests / total requests
        total   = len(error_window)
        errors  = sum(1 for x in error_window if x >= 400)
        uptime  = round(((total - errors) / total) * 100, 1) if total > 0 else 100.0

        p95 = round(float(np.percentile(latency_window, 95)), 1) if len(latency_window) >= 5 else round(avg_lat, 1)

        snapshot[endpoint] = {
            "status":         status,
            "avg_latency_ms": round(avg_lat, 1),
            "p95_latency_ms": p95,
            "error_rate":     round(err_rate, 3),
            "uptime_pct":     uptime,
            "sample_size":    len(latency_window),
        }
    return snapshot

async def run_anomaly_scan(sid: str, broadcast_fn):
    """Periodic scan to catch cross-endpoint cascade failures within one session."""
    snapshot            = await get_health_snapshot(sid)
    critical_endpoints  = [ep for ep, s in snapshot.items() if s["status"] == "critical"]
    total_endpoints     = len(snapshot) or 1

    key = "multi_endpoint_cascade"
    if len(critical_endpoints) >= 2:
        if await state.get_active_anomaly(sid, key) is None:
            affected_str = ", ".join(critical_endpoints[:3])
            # A real, computed number — the actual fraction of monitored
            # endpoints currently critical — not a hand-picked constant.
            cascade_confidence = round(len(critical_endpoints) / total_endpoints, 2)
            anomaly = {
                "detected_at":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                "anomaly_type":    "cascade_failure",
                "severity":        "critical",
                "endpoint":        "multiple",
                "description":     f"Cascade failure across {len(critical_endpoints)} endpoints ({affected_str}{'...' if len(critical_endpoints)>3 else ''}). Simultaneous failure across independently-monitored services suggests a shared dependency rather than isolated bugs.",
                "root_cause_chain": [
                    {"step": 1, "component": "Cross-endpoint correlation", "signal": f"{len(critical_endpoints)} of {total_endpoints} monitored endpoints critical simultaneously ({cascade_confidence*100:.0f}% of the fleet)", "confidence": cascade_confidence},
                    {"step": 2, "component": "Affected endpoints", "signal": affected_str, "confidence": cascade_confidence},
                ],
                "affected_endpoints": critical_endpoints,
            }
            await state.set_active_anomaly(sid, key, anomaly)
            anomaly_id = await insert_anomaly(sid, anomaly)
            anomaly["id"] = anomaly_id
            await broadcast_fn({"type": "anomaly", "data": anomaly})
    elif await state.get_active_anomaly(sid, key) is not None:
        await state.clear_active_anomaly(sid, key)
