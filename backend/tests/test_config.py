"""
Tests for backend/config.py

Validates:
- Default values match existing hardcoded behavior
- Environment variables override defaults
- Invalid values raise clear errors
- Invalid ranges are rejected
- Environment isolation between tests
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _reload_config():
    """Reload config module with current environment variables."""
    sys.modules.pop("config", None)
    import config  # noqa: F401
    importlib.reload(sys.modules["config"])
    return sys.modules["config"]


class TestDefaults:

    def test_default_zscore_threshold(self):
        config = _reload_config()
        assert config.ANOMALY_ZSCORE_THRESHOLD == 2.5

    def test_default_error_rate_threshold(self):
        config = _reload_config()
        assert config.ANOMALY_ERROR_RATE_THRESHOLD == 0.15

    def test_default_latency_threshold_ms(self):
        config = _reload_config()
        assert config.ANOMALY_LATENCY_THRESHOLD_MS == 250.0

    def test_default_zscore_clear_threshold(self):
        config = _reload_config()
        assert config.ANOMALY_ZSCORE_CLEAR_THRESHOLD == 1.5

    def test_default_error_rate_clear_threshold(self):
        config = _reload_config()
        assert config.ANOMALY_ERROR_RATE_CLEAR_THRESHOLD == 0.05


    class TestCustomValues:

        def test_custom_zscore_threshold(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_ZSCORE_THRESHOLD', '3.0')
            config = _reload_config()
            assert config.ANOMALY_ZSCORE_THRESHOLD == 3.0

        def test_custom_error_rate_threshold(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_ERROR_RATE_THRESHOLD', '0.20')
            config = _reload_config()
            assert config.ANOMALY_ERROR_RATE_THRESHOLD == 0.20

        def test_custom_latency_threshold_ms(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_LATENCY_THRESHOLD_MS', '500')
            config = _reload_config()
            assert config.ANOMALY_LATENCY_THRESHOLD_MS == 500.0

        def test_custom_zscore_clear_threshold(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_ZSCORE_CLEAR_THRESHOLD', '1.0')
            config = _reload_config()
            assert config.ANOMALY_ZSCORE_CLEAR_THRESHOLD == 1.0

        def test_custom_error_rate_clear_threshold(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_ERROR_RATE_CLEAR_THRESHOLD', '0.02')
            config = _reload_config()
            assert config.ANOMALY_ERROR_RATE_CLEAR_THRESHOLD == 0.02


    class TestInvalidValues:

        def test_non_numeric_zscore_raises(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_ZSCORE_THRESHOLD', 'abc')
            with pytest.raises(ValueError, match='Invalid value for SENTINEL_ANOMALY_ZSCORE_THRESHOLD'):
                _reload_config()

        def test_non_numeric_error_rate_raises(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_ERROR_RATE_THRESHOLD', 'not_a_number')
            with pytest.raises(ValueError, match='Invalid value for SENTINEL_ANOMALY_ERROR_RATE_THRESHOLD'):
                _reload_config()

        def test_non_numeric_latency_raises(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_LATENCY_THRESHOLD_MS', 'xyz')
            with pytest.raises(ValueError, match='Invalid value for SENTINEL_ANOMALY_LATENCY_THRESHOLD_MS'):
                _reload_config()


    class TestInvalidRanges:

        def test_negative_zscore_rejected(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_ZSCORE_THRESHOLD', '-1.0')
            with pytest.raises(ValueError, match='must be positive'):
                _reload_config()

        def test_zero_zscore_rejected(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_ZSCORE_THRESHOLD', '0')
            with pytest.raises(ValueError, match='must be positive'):
                _reload_config()

        def test_error_rate_above_one_rejected(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_ERROR_RATE_THRESHOLD', '1.5')
            with pytest.raises(ValueError, match='must be between 0 and 1'):
                _reload_config()

        def test_negative_error_rate_rejected(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_ERROR_RATE_THRESHOLD', '-0.1')
            with pytest.raises(ValueError, match='must be between 0 and 1'):
                _reload_config()

        def test_clear_threshold_not_less_than_detect_zscore_rejected(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_ZSCORE_CLEAR_THRESHOLD', '3.0')
            with pytest.raises(ValueError, match='must be less than'):
                _reload_config()

        def test_clear_threshold_not_less_than_detect_error_rate_rejected(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_ERROR_RATE_CLEAR_THRESHOLD', '0.20')
            with pytest.raises(ValueError, match='must be less than'):
                _reload_config()

        def test_negative_latency_rejected(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_LATENCY_THRESHOLD_MS', '-10')
            with pytest.raises(ValueError, match='must be between 0 and 10000'):
                _reload_config()


    class TestEnvironmentIsolation:

        def test_env_not_leaked_between_tests(self, monkeypatch):
            monkeypatch.setenv('SENTINEL_ANOMALY_ZSCORE_THRESHOLD', '-1')
            with pytest.raises(ValueError, match='must be positive'):
                _reload_config()
            monkeypatch.delenv('SENTINEL_ANOMALY_ZSCORE_THRESHOLD', raising=False)
            config = _reload_config()
            assert config.ANOMALY_ZSCORE_THRESHOLD == 2.5
