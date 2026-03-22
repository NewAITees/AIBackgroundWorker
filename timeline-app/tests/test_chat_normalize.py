"""_normalize_candidates のユニットテスト。"""

from __future__ import annotations

from src.routers.chat import _normalize_candidates


def test_normalizes_basic_candidate():
    raw = [{"type": "todo", "content": "やること"}]
    result = _normalize_candidates(raw)
    assert len(result) == 1
    assert result[0]["type"] == "todo"
    assert result[0]["content"] == "やること"


def test_preserves_timestamp():
    ts = "2026-03-22T15:00:00+09:00"
    raw = [{"type": "event", "content": "会議", "timestamp": ts}]
    result = _normalize_candidates(raw)
    assert result[0]["timestamp"] == ts


def test_timestamp_is_none_when_absent():
    raw = [{"type": "memo", "content": "メモ"}]
    result = _normalize_candidates(raw)
    assert result[0]["timestamp"] is None


def test_filters_invalid_type():
    raw = [{"type": "invalid_type", "content": "内容"}]
    assert _normalize_candidates(raw) == []


def test_filters_empty_content():
    raw = [{"type": "diary", "content": ""}]
    assert _normalize_candidates(raw) == []


def test_filters_whitespace_only_content():
    raw = [{"type": "todo", "content": "   "}]
    assert _normalize_candidates(raw) == []


def test_limits_to_three():
    raw = [{"type": "memo", "content": f"内容{i}"} for i in range(5)]
    assert len(_normalize_candidates(raw)) == 3


def test_preserves_title():
    raw = [{"type": "event", "title": "会議", "content": "詳細説明"}]
    result = _normalize_candidates(raw)
    assert result[0]["title"] == "会議"


def test_title_is_none_when_absent():
    raw = [{"type": "todo", "content": "やること"}]
    result = _normalize_candidates(raw)
    assert result[0]["title"] is None


def test_strips_whitespace_from_content():
    raw = [{"type": "memo", "content": "  メモ内容  "}]
    result = _normalize_candidates(raw)
    assert result[0]["content"] == "メモ内容"


def test_all_valid_types_accepted():
    for entry_type in ("diary", "event", "todo", "memo"):
        raw = [{"type": entry_type, "content": "内容"}]
        result = _normalize_candidates(raw)
        assert len(result) == 1, f"{entry_type} が受け付けられない"


def test_empty_input_returns_empty():
    assert _normalize_candidates([]) == []


def test_mixed_valid_and_invalid():
    raw = [
        {"type": "todo", "content": "有効"},
        {"type": "invalid", "content": "無効"},
        {"type": "diary", "content": "有効2"},
    ]
    result = _normalize_candidates(raw)
    assert len(result) == 2
    assert result[0]["content"] == "有効"
    assert result[1]["content"] == "有効2"
