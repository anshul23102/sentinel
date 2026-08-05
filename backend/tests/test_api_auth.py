"""
Unit tests for the API-key guard on the Groq-backed / state-mutating routes.
Issue #43 - https://github.com/anshul23102/sentinel/issues/43
"""

import pytest
from fastapi import HTTPException

from main import require_api_key


def test_no_api_key_configured_is_a_no_op(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    # Should not raise even with no header (local-dev convenience).
    assert require_api_key(None) is None


def test_wrong_or_missing_key_is_rejected(monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")
    with pytest.raises(HTTPException) as missing:
        require_api_key(None)
    assert missing.value.status_code == 401
    with pytest.raises(HTTPException):
        require_api_key("wrong")


def test_correct_key_passes(monkeypatch):
    monkeypatch.setenv("API_KEY", "s3cret")
    assert require_api_key("s3cret") is None
