"""
Unit tests for backend/ai_agent._summarize_logs
Issue #42 - https://github.com/anshul23102/sentinel/issues/42

The summary fed to the LLM must count failures at the same threshold the
anomaly detector uses (>= 400), so a 4xx surge (e.g. 429 rate-limit cascade)
isn't reported to the model as "0 errors".
"""

from ai_agent import _summarize_logs


def _log(status, endpoint="/api/x", latency=10, msg=None):
    return {
        "endpoint": endpoint,
        "status_code": status,
        "latency_ms": latency,
        "error_message": msg,
    }


def test_summarize_counts_4xx_failures():
    logs = [
        _log(200),
        _log(429, msg="rate limited"),
        _log(429, msg="rate limited"),
        _log(500, msg="boom"),
    ]
    summary = _summarize_logs(logs, "/api/x")

    # Two 429s + one 500 = 3 failures, not just the single 5xx.
    assert summary["error_count"] == 3
    assert summary["error_rate"] == round(3 / 4, 3)
    assert "rate limited" in summary["unique_error_messages"]


def test_summarize_reports_no_errors_for_all_success():
    logs = [_log(200), _log(304)]
    summary = _summarize_logs(logs, "/api/x")

    assert summary["error_count"] == 0
    assert summary["error_rate"] == 0
