"""
Regression tests for issue #71 — the anomaly-detection windows were bounded by
SAMPLE COUNT (deque(maxlen=60)) while the design treats them as "60 seconds of
data". They only coincide at ~1 req/s, so busy endpoints kept only a few seconds
(spikes missed) and quiet endpoints kept minutes (stale health lingered).

Windows are now time-based; a fake monotonic clock drives eviction deterministically.
"""

import pytest

import anomaly_detector
from anomaly_detector import (
    process_log_batch,
    get_health_snapshot,
    _latency_windows,
    _error_windows,
    _request_windows,
    _active_anomalies,
    WINDOW_SECONDS,
)


def _reset():
    _latency_windows.clear()
    _error_windows.clear()
    _request_windows.clear()
    _active_anomalies.clear()


@pytest.fixture(autouse=True)
def reset_state():
    _reset()
    yield
    _reset()


def _logs(ep, latency=80.0, status=200, n=1):
    return [{"endpoint": ep, "latency_ms": latency, "status_code": status}] * n


def test_window_bounded_by_time_not_sample_count(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(anomaly_detector.time, "monotonic", lambda: clock["t"])

    # 100 logs in one instant. The old deque(maxlen=60) capped the window at 60;
    # a time-based window at a single instant keeps all 100.
    process_log_batch(_logs("/api/busy", n=100))
    assert len(_latency_windows["/api/busy"]) == 100
    assert len(_error_windows["/api/busy"]) == 100

    # Advance past the window — the 100 stale samples must evict on next append.
    clock["t"] = 1000.0 + WINDOW_SECONDS + 1
    process_log_batch(_logs("/api/busy", n=1))
    assert len(_latency_windows["/api/busy"]) == 1
    assert len(_error_windows["/api/busy"]) == 1


def test_partial_eviction_keeps_in_window_samples(monkeypatch):
    clock = {"t": 500.0}
    monkeypatch.setattr(anomaly_detector.time, "monotonic", lambda: clock["t"])

    process_log_batch(_logs("/api/x", n=10))       # t=500
    clock["t"] = 500.0 + 30
    process_log_batch(_logs("/api/x", n=5))        # t=530, still inside 60s
    assert len(_error_windows["/api/x"]) == 15

    clock["t"] = 500.0 + 61                         # first batch now > 60s old
    process_log_batch(_logs("/api/x", n=1))        # t=561
    # The 10 at t=500 evict; the 5 at t=530 plus the new 1 remain.
    assert len(_error_windows["/api/x"]) == 6


def test_quiet_endpoint_health_clears_after_window(monkeypatch):
    clock = {"t": 5000.0}
    monkeypatch.setattr(anomaly_detector.time, "monotonic", lambda: clock["t"])

    process_log_batch(_logs("/api/quiet", latency=700.0, status=500, n=20))
    assert get_health_snapshot()["/api/quiet"]["status"] == "critical"

    # 61s pass with no new traffic. Old code kept the stale samples and reported
    # "critical" forever; now they evict and the endpoint drops out of the snapshot.
    clock["t"] = 5000.0 + WINDOW_SECONDS + 1
    assert "/api/quiet" not in get_health_snapshot()


def test_busy_endpoint_retains_full_60s_baseline(monkeypatch):
    """At ~8 req/s a real 60s window holds ~480 samples — far more than the old 60,
    so a gradual ramp is measured against a true 60s baseline instead of ~8s."""
    clock = {"t": 0.0}
    monkeypatch.setattr(anomaly_detector.time, "monotonic", lambda: clock["t"])

    # 8 logs/second for 60 seconds.
    for second in range(60):
        clock["t"] = float(second)
        process_log_batch(_logs("/api/products", latency=80.0, n=8))

    assert len(_latency_windows["/api/products"]) == 60 * 8  # 480, not capped at 60
