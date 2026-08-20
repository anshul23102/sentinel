"""
Regression test for issue #70 — a malformed `history` item crashed
POST /api/chat with an unhandled 500 because the replay loop indexed
msg["role"]/msg["content"] directly.

_clean_history is pure (no Groq client needed), so we test it directly.
"""

from ai_agent import _clean_history


def test_well_formed_history_passes_through():
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    assert _clean_history(history) == history


def test_item_missing_role_is_skipped_not_crashing():
    # This is the exact payload from the issue: { "foo": "bar" }
    assert _clean_history([{"foo": "bar"}]) == []


def test_partially_malformed_history_keeps_the_good_items():
    history = [
        {"role": "user", "content": "keep me"},
        {"content": "no role"},
        {"role": "assistant"},          # no content
        {"role": "user", "content": "keep me too"},
    ]
    assert _clean_history(history) == [
        {"role": "user", "content": "keep me"},
        {"role": "user", "content": "keep me too"},
    ]


def test_non_dict_items_are_skipped():
    assert _clean_history(["a string", 42, None, {"role": "user", "content": "ok"}]) == [
        {"role": "user", "content": "ok"}
    ]


def test_non_string_role_or_content_is_skipped():
    assert _clean_history([{"role": 1, "content": "x"}, {"role": "user", "content": {"nested": 1}}]) == []


def test_empty_and_none_history():
    assert _clean_history([]) == []
    assert _clean_history(None) == []


def test_only_last_8_turns_are_replayed():
    history = [{"role": "user", "content": str(i)} for i in range(20)]
    cleaned = _clean_history(history)
    assert len(cleaned) == 8
    assert cleaned[0]["content"] == "12"   # 20 - 8
    assert cleaned[-1]["content"] == "19"
