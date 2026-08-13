"""
Centralized configuration for Sentinel anomaly detection thresholds.

All anomaly-detection sensitivity values are loaded from environment variables
with sensible defaults that preserve the existing hardcoded behavior.
"""

from __future__ import annotations

import os


def _load_float(name: str, default: float, validator) -> float:
    """Load a float from env, validate it, or use default."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(
            f"Invalid value for {name}: '{raw}'. "
            f"Expected a number, got '{raw}'."
        ) from None
    return validator(value, name)


def _validate_zscore(value: float, name: str) -> float:
    if value <= 0:
        raise ValueError(
            f"{name} must be positive (got {value}). "
            f"A Z-score threshold must be greater than zero."
        )
    return value


def _validate_rate(value: float, name: str, max_value: float = 1.0) -> float:
    if not (0.0 <= value <= max_value):
        raise ValueError(
            f"{name} must be between 0 and {max_value} (got {value})."
        )
    return value


def _validate_clear_vs_detect(clear: float, detect: float, clear_name: str, detect_name: str) -> float:
    if clear >= detect:
        raise ValueError(
            f"{clear_name} ({clear}) must be less than {detect_name} ({detect}) "
            f"so anomalies can clear."
        )
    return clear


# ---------------------------------------------------------------------------
# Anomaly detection thresholds
# ---------------------------------------------------------------------------

#: Z-score above which a latency spike is flagged.
ANOMALY_ZSCORE_THRESHOLD: float = _load_float(
    "SENTINEL_ANOMALY_ZSCORE_THRESHOLD",
    2.5,
    _validate_zscore,
)

#: Error rate (fraction of 4xx/5xx responses) above which an error surge is flagged.
ANOMALY_ERROR_RATE_THRESHOLD: float = _load_float(
    "SENTINEL_ANOMALY_ERROR_RATE_THRESHOLD",
    0.15,
    lambda v, n: _validate_rate(v, n),
)

#: Minimum average latency (ms) that must be exceeded for a latency spike to be considered.
ANOMALY_LATENCY_THRESHOLD_MS: float = _load_float(
    "SENTINEL_ANOMALY_LATENCY_THRESHOLD_MS",
    250.0,
    lambda v, n: _validate_rate(v, n, max_value=10000.0),
)

#: Z-score below which a previously-firing latency anomaly is cleared.
ANOMALY_ZSCORE_CLEAR_THRESHOLD: float = _load_float(
    "SENTINEL_ANOMALY_ZSCORE_CLEAR_THRESHOLD",
    1.5,
    lambda v, n: _validate_clear_vs_detect(v, ANOMALY_ZSCORE_THRESHOLD, n, "ANOMALY_ZSCORE_THRESHOLD"),
)

#: Error rate below which a previously-firing error anomaly is cleared.
ANOMALY_ERROR_RATE_CLEAR_THRESHOLD: float = _load_float(
    "SENTINEL_ANOMALY_ERROR_RATE_CLEAR_THRESHOLD",
    0.05,
    lambda v, n: _validate_clear_vs_detect(v, ANOMALY_ERROR_RATE_THRESHOLD, n, "ANOMALY_ERROR_RATE_THRESHOLD"),
)
