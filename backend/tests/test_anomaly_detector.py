"""
Unit tests for backend/anomaly_detector.py
Issue #4 - https://github.com/anshul23102/sentinel/issues/4

Tests cover:
- Normal traffic (no anomaly)
- Latency spike detection via Z-score
- Error rate surge detection
- Health snapshot / health scoring
- Edge cases (insufficient data, zero std dev)
"""

import pytest
from collections import deque

from anomaly_detector import (
    process_log_batch,
    get_health_snapshot,
    _latency_windows,
    _error_windows,
    _request_windows,
    _active_anomalies,
    LATENCY_Z_THRESHOLD,
    ERROR_RATE_THRESHOLD,
    _z_score,
    _error_rate,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _reset():
    """Clear all module-level state between tests."""
    _latency_windows.clear()
    _error_windows.clear()
    _request_windows.clear()
    _active_anomalies.clear()


def _make_logs(endpoint: str, latency_ms: float, status_code: int = 200, n: int = 1) -> list[dict]:
    return [{"endpoint": endpoint, "latency_ms": latency_ms, "status_code": status_code}] * n


@pytest.fixture(autouse=True)
def reset_state():
    """Automatically reset module state before every test."""
    _reset()
    yield
    _reset()


# ===========================================================================
# Z-score helper tests
# ===========================================================================

class TestZscoreHelper:

    def test_returns_zero_when_insufficient_data(self):
        """Fewer than 10 samples should return 0.0, not raise."""
        window = deque([80.0] * 5, maxlen=60)
        assert _z_score(2000.0, window) == 0.0

    def test_returns_zero_when_std_is_zero(self):
        """All identical values -> std=0 -> should return 0.0."""
        window = deque([100.0] * 20, maxlen=60)
        assert _z_score(100.0, window) == 0.0

    def test_large_spike_gives_high_zscore(self):
        """A spike value already inside a mixed window should produce Z > threshold."""
        # Simulate what process_log_batch does: append the spike first, then call _z_score
        window = deque([80.0] * 55 + [2000.0] * 5, maxlen=60)
        z = _z_score(2000.0, window)
        assert z > LATENCY_Z_THRESHOLD

    def test_normal_value_gives_low_zscore(self):
        """A value close to the mean should produce a small Z-score."""
        # Use a window with natural variation (70-90) so std is ~6ms
        import random
        random.seed(42)
        window = deque([random.uniform(70, 90) for _ in range(60)], maxlen=60)
        z = _z_score(80.0, window)  # 80ms is right in the middle of the range
        assert abs(z) < 1.0


# ===========================================================================
# Error rate helper tests
# ===========================================================================

class TestErrorRateHelper:

    def test_no_errors(self):
        window = deque([200] * 20, maxlen=60)
        assert _error_rate(window) == 0.0

    def test_all_errors(self):
        window = deque([500] * 20, maxlen=60)
        assert _error_rate(window) == 1.0

    def test_mixed(self):
        window = deque([200] * 8 + [500] * 2, maxlen=60)
        assert abs(_error_rate(window) - 0.2) < 1e-9

    def test_empty_window(self):
        assert _error_rate(deque(maxlen=60)) == 0.0


# ===========================================================================
# process_log_batch - normal traffic
# ===========================================================================

class TestNormalTraffic:

    def test_no_anomaly_on_normal_traffic(self):
        """Stable low-latency traffic should produce zero anomalies."""
        anomalies = process_log_batch(_make_logs("/api/checkout", latency_ms=80.0, n=30))
        assert anomalies == []

    def test_no_anomaly_on_moderate_latency_increase(self):
        """A slight uptick should not cross the Z-score threshold."""
        process_log_batch(_make_logs("/api/auth", latency_ms=80.0, n=55))
        anomalies = process_log_batch(_make_logs("/api/auth", latency_ms=100.0, n=5))
        assert anomalies == []

    def test_returns_list(self):
        """process_log_batch must always return a list."""
        result = process_log_batch(_make_logs("/api/search", latency_ms=80.0, n=5))
        assert isinstance(result, list)


# ===========================================================================
# process_log_batch - latency spike detection
# ===========================================================================

class TestLatencySpikeDetection:

    def test_latency_spike_detected(self):
        """A spike well above 250 ms against a large stable baseline must be flagged."""
        # Need a big baseline so the spike batch doesn't dominate the std
        process_log_batch(_make_logs("/api/checkout", latency_ms=80.0, n=55))
        anomalies = process_log_batch(_make_logs("/api/checkout", latency_ms=2000.0, n=5))
        types = [a["anomaly_type"] for a in anomalies]
        assert "latency_spike" in types

    def test_latency_spike_anomaly_fields(self):
        """A latency_spike anomaly must contain the required fields."""
        process_log_batch(_make_logs("/api/checkout", latency_ms=80.0, n=55))
        anomalies = process_log_batch(_make_logs("/api/checkout", latency_ms=2000.0, n=5))
        spike = next(a for a in anomalies if a["anomaly_type"] == "latency_spike")
        for field in ("detected_at", "severity", "endpoint", "description", "z_score", "avg_latency"):
            assert field in spike, f"Missing field: {field}"

    def test_spike_below_250ms_not_flagged(self):
        """Even a high Z-score must not fire if avg latency <= 250 ms."""
        process_log_batch(_make_logs("/api/products", latency_ms=10.0, n=55))
        anomalies = process_log_batch(_make_logs("/api/products", latency_ms=200.0, n=5))
        types = [a["anomaly_type"] for a in anomalies]
        assert "latency_spike" not in types

    def test_insufficient_data_no_spike_flagged(self):
        """With fewer than 10 baseline samples Z-score returns 0 - no spike."""
        anomalies = process_log_batch(_make_logs("/api/auth", latency_ms=2000.0, n=3))
        types = [a["anomaly_type"] for a in anomalies]
        assert "latency_spike" not in types

    def test_separate_endpoints_are_independent(self):
        """A spike on one endpoint must not affect another."""
        process_log_batch(_make_logs("/api/checkout", latency_ms=80.0, n=55))
        process_log_batch(_make_logs("/api/auth", latency_ms=80.0, n=55))
        process_log_batch(_make_logs("/api/checkout", latency_ms=2000.0, n=5))
        anomalies = process_log_batch(_make_logs("/api/auth", latency_ms=82.0, n=2))
        types = [a["anomaly_type"] for a in anomalies]
        assert "latency_spike" not in types


# ===========================================================================
# process_log_batch - error rate surge detection
# ===========================================================================

class TestErrorSurgeDetection:

    def test_error_surge_detected(self):
        """Error rate above ERROR_RATE_THRESHOLD must produce an error_surge anomaly."""
        anomalies = process_log_batch(_make_logs("/api/cart", latency_ms=80.0, status_code=500, n=40))
        types = [a["anomaly_type"] for a in anomalies]
        assert "error_surge" in types

    def test_error_surge_anomaly_fields(self):
        """An error_surge anomaly must contain required fields."""
        anomalies = process_log_batch(_make_logs("/api/cart", latency_ms=80.0, status_code=500, n=40))
        surge = next(a for a in anomalies if a["anomaly_type"] == "error_surge")
        for field in ("detected_at", "severity", "endpoint", "description", "error_rate"):
            assert field in surge, f"Missing field: {field}"

    def test_low_error_rate_no_surge(self):
        """Error rate well below threshold should not trigger error_surge."""
        logs = _make_logs("/api/inventory", latency_ms=80.0, status_code=200, n=19)
        logs += _make_logs("/api/inventory", latency_ms=80.0, status_code=500, n=1)
        anomalies = process_log_batch(logs)
        types = [a["anomaly_type"] for a in anomalies]
        assert "error_surge" not in types

    def test_4xx_counts_as_error(self):
        """4xx responses must count toward the error rate."""
        anomalies = process_log_batch(_make_logs("/api/auth", latency_ms=80.0, status_code=429, n=40))
        types = [a["anomaly_type"] for a in anomalies]
        assert "error_surge" in types
    
    def test_error_rate_exactly_at_threshold_triggers_surge(self):
        """Error rate at or above ERROR_RATE_THRESHOLD must trigger error_surge."""
        n_errors = int(20 * ERROR_RATE_THRESHOLD) + 1
        logs = _make_logs("/api/orders", latency_ms=80.0, status_code=200, n=20 - n_errors)
        logs += _make_logs("/api/orders", latency_ms=80.0, status_code=500, n=n_errors)
        anomalies = process_log_batch(logs)
        types = [a["anomaly_type"] for a in anomalies]
        assert "error_surge" in types


# ===========================================================================
# get_health_snapshot tests
# ===========================================================================

class TestHealthSnapshot:

    def test_empty_snapshot_on_no_data(self):
        """With no logs processed, snapshot should be empty."""
        assert get_health_snapshot() == {}

    def test_healthy_status_on_normal_traffic(self):
        """Low latency, no errors -> status should be 'healthy'."""
        process_log_batch(_make_logs("/api/checkout", latency_ms=80.0, n=30))
        snapshot = get_health_snapshot()
        assert snapshot["/api/checkout"]["status"] == "healthy"

    def test_critical_status_on_high_error_rate(self):
        """Error rate > 28% -> status should be 'critical'."""
        process_log_batch(_make_logs("/api/cart", latency_ms=80.0, status_code=500, n=40))
        snapshot = get_health_snapshot()
        assert snapshot["/api/cart"]["status"] == "critical"

    def test_critical_status_on_high_latency(self):
        """Avg latency > 600 ms -> status should be 'critical'."""
        process_log_batch(_make_logs("/api/search", latency_ms=700.0, n=20))
        snapshot = get_health_snapshot()
        assert snapshot["/api/search"]["status"] == "critical"

    def test_snapshot_contains_required_fields(self):
        """Each endpoint entry must have the expected keys."""
        process_log_batch(_make_logs("/api/auth", latency_ms=80.0, n=10))
        snapshot = get_health_snapshot()
        entry = snapshot["/api/auth"]
        for field in ("status", "avg_latency_ms", "p95_latency_ms", "error_rate", "uptime_pct", "sample_size"):
            assert field in entry, f"Missing field: {field}"

    def test_uptime_100_on_no_errors(self):
        """Zero errors -> uptime should be 100.0."""
        process_log_batch(_make_logs("/api/products", latency_ms=80.0, n=20))
        snapshot = get_health_snapshot()
        assert snapshot["/api/products"]["uptime_pct"] == 100.0

    def test_uptime_drops_with_errors(self):
        """Errors must reduce uptime below 100."""
        process_log_batch(_make_logs("/api/products", latency_ms=80.0, status_code=500, n=10))
        snapshot = get_health_snapshot()
        assert snapshot["/api/products"]["uptime_pct"] < 100.0
