"""
全 entry type の CRUD（POST → GET → PATCH → timeline）テスト。

対象:
  chat_user / chat_ai / diary / event / todo / todo_done / news / system_log / memo
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _create(client: TestClient, entry_type: str, content: str, source: str = "user", **kwargs):
    """POST /api/entries を呼んで (entry_id, response_json) を返す。"""
    payload = {"type": entry_type, "content": content, "source": source, **kwargs}
    resp = client.post("/api/entries", json=payload)
    assert resp.status_code == 201, f"{entry_type} 作成失敗: {resp.text}"
    data = resp.json()
    return data["id"], data


def _get(client: TestClient, entry_id: str):
    resp = client.get(f"/api/entries/{entry_id}")
    assert resp.status_code == 200, f"GET 失敗: {resp.text}"
    return resp.json()


def _patch(client: TestClient, entry_id: str, **fields):
    resp = client.patch(f"/api/entries/{entry_id}", json=fields)
    assert resp.status_code == 200, f"PATCH 失敗: {resp.text}"
    return resp.json()


def _timeline_ids(client: TestClient) -> set[str]:
    resp = client.get("/api/timeline")
    assert resp.status_code == 200
    data = resp.json()
    ids = set()
    for section in ("future_entries", "todo_entries", "past_entries"):
        ids.update(e["id"] for e in data.get(section, []))
    return ids


# ---------------------------------------------------------------------------
# diary
# ---------------------------------------------------------------------------


class TestDiaryEntry:
    def test_create(self, client: TestClient):
        _, data = _create(client, "diary", "今日は良い天気だった。")
        assert data["type"] == "diary"
        assert data["content"] == "今日は良い天気だった。"
        assert data["status"] == "active"

    def test_get_roundtrip(self, client: TestClient):
        eid, _ = _create(client, "diary", "日記の内容")
        data = _get(client, eid)
        assert data["id"] == eid
        assert data["type"] == "diary"
        assert data["content"] == "日記の内容"

    def test_patch_content(self, client: TestClient):
        eid, _ = _create(client, "diary", "元の内容")
        data = _patch(client, eid, content="更新後の内容")
        assert data["content"] == "更新後の内容"

    def test_patch_title(self, client: TestClient):
        eid, _ = _create(client, "diary", "日記")
        data = _patch(client, eid, title="タイトル付き日記")
        assert data["title"] == "タイトル付き日記"

    def test_appears_on_timeline(self, client: TestClient):
        eid, _ = _create(client, "diary", "タイムラインに乗るか")
        assert eid in _timeline_ids(client)


# ---------------------------------------------------------------------------
# event
# ---------------------------------------------------------------------------


class TestEventEntry:
    def test_create(self, client: TestClient):
        _, data = _create(client, "event", "会議に出席した")
        assert data["type"] == "event"

    def test_create_with_future_timestamp(self, client: TestClient):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        _, data = _create(client, "event", "明日の予定", timestamp=future)
        ts = datetime.fromisoformat(data["timestamp"])
        assert ts > datetime.now(timezone.utc)

    def test_get_roundtrip(self, client: TestClient):
        eid, _ = _create(client, "event", "イベント内容")
        data = _get(client, eid)
        assert data["type"] == "event"

    def test_patch_content(self, client: TestClient):
        eid, _ = _create(client, "event", "元の出来事")
        data = _patch(client, eid, content="修正後の出来事")
        assert data["content"] == "修正後の出来事"

    def test_appears_on_timeline(self, client: TestClient):
        eid, _ = _create(client, "event", "タイムライン確認用イベント")
        assert eid in _timeline_ids(client)


# ---------------------------------------------------------------------------
# todo / todo_done
# ---------------------------------------------------------------------------


class TestTodoEntry:
    def test_create(self, client: TestClient):
        _, data = _create(client, "todo", "買い物リストを作る")
        assert data["type"] == "todo"

    def test_default_timestamp_is_near_future(self, client: TestClient):
        before = datetime.now(timezone.utc)
        _, data = _create(client, "todo", "近未来 TODO")
        after = datetime.now(timezone.utc)
        ts = datetime.fromisoformat(data["timestamp"])
        assert before + timedelta(minutes=4) <= ts <= after + timedelta(minutes=7)

    def test_explicit_timestamp_respected(self, client: TestClient):
        future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        _, data = _create(client, "todo", "3日後のタスク", timestamp=future)
        ts = datetime.fromisoformat(data["timestamp"])
        assert ts > datetime.now(timezone.utc) + timedelta(days=2)

    def test_get_roundtrip(self, client: TestClient):
        eid, _ = _create(client, "todo", "取得確認用 TODO")
        data = _get(client, eid)
        assert data["type"] == "todo"

    def test_appears_on_timeline_future_section(self, client: TestClient):
        eid, _ = _create(client, "todo", "未来セクション確認")
        resp = client.get("/api/timeline")
        all_ids = {e["id"] for e in resp.json().get("todo_entries", [])} | {
            e["id"] for e in resp.json().get("future_entries", [])
        }
        assert eid in all_ids

    def test_complete_todo_updates_type(self, client: TestClient):
        eid, _ = _create(client, "todo", "完了するタスク")
        data = _patch(client, eid, type="todo_done", status="done")
        assert data["type"] == "todo_done"
        assert data["status"] == "done"

    def test_complete_todo_sets_timestamp_to_now(self, client: TestClient):
        eid, _ = _create(client, "todo", "完了タイムスタンプ確認")
        before = datetime.now(timezone.utc)
        data = _patch(client, eid, type="todo_done")
        after = datetime.now(timezone.utc)
        ts = datetime.fromisoformat(data["timestamp"])
        assert before <= ts <= after

    def test_complete_todo_with_explicit_timestamp(self, client: TestClient):
        eid, _ = _create(client, "todo", "明示 timestamp で完了")
        explicit = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        data = _patch(client, eid, type="todo_done", timestamp=explicit)
        ts = datetime.fromisoformat(data["timestamp"])
        assert ts <= datetime.now(timezone.utc) - timedelta(minutes=50)


class TestTodoDoneEntry:
    def test_create_directly(self, client: TestClient):
        _, data = _create(client, "todo_done", "最初から完了状態")
        assert data["type"] == "todo_done"

    def test_get_roundtrip(self, client: TestClient):
        eid, _ = _create(client, "todo_done", "完了済みタスク")
        data = _get(client, eid)
        assert data["type"] == "todo_done"

    def test_appears_on_timeline(self, client: TestClient):
        eid, _ = _create(client, "todo_done", "タイムライン確認")
        assert eid in _timeline_ids(client)


# ---------------------------------------------------------------------------
# memo
# ---------------------------------------------------------------------------


class TestMemoEntry:
    def test_create(self, client: TestClient):
        _, data = _create(client, "memo", "メモの内容です")
        assert data["type"] == "memo"

    def test_get_roundtrip(self, client: TestClient):
        eid, _ = _create(client, "memo", "取得確認メモ")
        data = _get(client, eid)
        assert data["type"] == "memo"
        assert data["content"] == "取得確認メモ"

    def test_patch_content(self, client: TestClient):
        eid, _ = _create(client, "memo", "元のメモ")
        data = _patch(client, eid, content="書き直したメモ")
        assert data["content"] == "書き直したメモ"

    def test_patch_status_to_archived(self, client: TestClient):
        eid, _ = _create(client, "memo", "アーカイブするメモ")
        data = _patch(client, eid, status="archived")
        assert data["status"] == "archived"

    def test_appears_on_timeline(self, client: TestClient):
        eid, _ = _create(client, "memo", "タイムライン確認メモ")
        assert eid in _timeline_ids(client)


# ---------------------------------------------------------------------------
# news
# ---------------------------------------------------------------------------


class TestNewsEntry:
    def test_create(self, client: TestClient):
        _, data = _create(client, "news", "Python 4.0 がリリースされた", source="imported")
        assert data["type"] == "news"
        assert data["source"] == "imported"

    def test_create_with_title(self, client: TestClient):
        _, data = _create(client, "news", "本文内容", source="imported", title="ニュースタイトル")
        assert data["title"] == "ニュースタイトル"

    def test_get_roundtrip(self, client: TestClient):
        eid, _ = _create(client, "news", "ニュース内容")
        data = _get(client, eid)
        assert data["type"] == "news"

    def test_patch_content(self, client: TestClient):
        eid, _ = _create(client, "news", "元のニュース")
        data = _patch(client, eid, content="更新後のニュース")
        assert data["content"] == "更新後のニュース"

    def test_appears_on_timeline(self, client: TestClient):
        eid, _ = _create(client, "news", "タイムライン確認ニュース")
        assert eid in _timeline_ids(client)


# ---------------------------------------------------------------------------
# system_log
# ---------------------------------------------------------------------------


class TestSystemLogEntry:
    def test_create(self, client: TestClient):
        _, data = _create(client, "system_log", "ブラウザ履歴の1時間サマリー", source="system")
        assert data["type"] == "system_log"
        assert data["source"] == "system"

    def test_create_with_summary(self, client: TestClient):
        _, data = _create(
            client,
            "system_log",
            "詳細な活動ログ本文",
            source="system",
            summary="短い要約テキスト",
        )
        assert data["summary"] == "短い要約テキスト"
        assert data["content"] == "詳細な活動ログ本文"

    def test_get_roundtrip(self, client: TestClient):
        eid, _ = _create(client, "system_log", "システムログ内容", source="system")
        data = _get(client, eid)
        assert data["type"] == "system_log"

    def test_patch_content(self, client: TestClient):
        eid, _ = _create(client, "system_log", "元のログ", source="system")
        data = _patch(client, eid, content="更新後のログ")
        assert data["content"] == "更新後のログ"

    def test_appears_on_timeline(self, client: TestClient):
        eid, _ = _create(client, "system_log", "タイムライン確認ログ", source="system")
        assert eid in _timeline_ids(client)


# ---------------------------------------------------------------------------
# chat_user / chat_ai
# ---------------------------------------------------------------------------


class TestChatUserEntry:
    def test_create(self, client: TestClient):
        _, data = _create(client, "chat_user", "今日は何をしようか", source="user")
        assert data["type"] == "chat_user"

    def test_get_roundtrip(self, client: TestClient):
        eid, _ = _create(client, "chat_user", "ユーザー発言内容")
        data = _get(client, eid)
        assert data["type"] == "chat_user"

    def test_appears_on_timeline(self, client: TestClient):
        eid, _ = _create(client, "chat_user", "タイムライン確認チャット")
        assert eid in _timeline_ids(client)


class TestChatAiEntry:
    def test_create(self, client: TestClient):
        _, data = _create(client, "chat_ai", "いいですね、試してみましょう", source="ai")
        assert data["type"] == "chat_ai"
        assert data["source"] == "ai"

    def test_get_roundtrip(self, client: TestClient):
        eid, _ = _create(client, "chat_ai", "AI返答内容", source="ai")
        data = _get(client, eid)
        assert data["type"] == "chat_ai"

    def test_appears_on_timeline(self, client: TestClient):
        eid, _ = _create(client, "chat_ai", "タイムライン確認AI", source="ai")
        assert eid in _timeline_ids(client)


# ---------------------------------------------------------------------------
# 横断テスト: 全 type が POST → GET で type を保持すること
# ---------------------------------------------------------------------------


ALL_TYPES = [
    ("diary", "user"),
    ("event", "user"),
    ("todo", "user"),
    ("todo_done", "user"),
    ("memo", "user"),
    ("news", "imported"),
    ("system_log", "system"),
    ("chat_user", "user"),
    ("chat_ai", "ai"),
]


@pytest.mark.parametrize("entry_type,source", ALL_TYPES)
def test_all_types_create_and_get(client: TestClient, entry_type: str, source: str):
    """全 entry type が作成・取得できること。"""
    eid, created = _create(client, entry_type, f"{entry_type}のテスト内容", source=source)
    assert created["type"] == entry_type
    fetched = _get(client, eid)
    assert fetched["type"] == entry_type
    assert fetched["content"] == f"{entry_type}のテスト内容"


@pytest.mark.parametrize("entry_type,source", ALL_TYPES)
def test_all_types_appear_on_timeline(client: TestClient, entry_type: str, source: str):
    """全 entry type がタイムラインに表示されること。"""
    eid, _ = _create(client, entry_type, f"timeline確認 {entry_type}", source=source)
    assert eid in _timeline_ids(client)
