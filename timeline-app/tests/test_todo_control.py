"""todo_control.md ストレージと migrate エンドポイントのテスト。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import yaml
from fastapi.testclient import TestClient

from src.storage.todo_control import (
    find_todo,
    read_todo_control,
    remove_todo,
    upsert_todo,
    write_todo_control,
)
from src.models.entry import Entry, EntryStatus, EntryType


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture()
def ws(tmp_path) -> str:
    return str(tmp_path)


def _make_todo(ws: str, entry_id: str = "test-id-001") -> Entry:
    return Entry(
        id=entry_id,
        type=EntryType.todo,
        content="テストTODO",
        timestamp=datetime.now(timezone.utc),
        status=EntryStatus.active,
        source="user",
        workspace_path=ws,
    )


# ---------------------------------------------------------------------------
# read_todo_control
# ---------------------------------------------------------------------------


class TestReadTodoControl:
    def test_returns_empty_when_file_missing(self, ws: str):
        assert read_todo_control(ws, "todo_control.md") == []

    def test_returns_empty_on_yaml_error(self, ws: str, tmp_path):
        (tmp_path / "todo_control.md").write_text(": invalid: yaml: [", encoding="utf-8")
        assert read_todo_control(ws, "todo_control.md") == []

    def test_returns_empty_on_non_list_yaml(self, ws: str, tmp_path):
        (tmp_path / "todo_control.md").write_text("key: value\n", encoding="utf-8")
        assert read_todo_control(ws, "todo_control.md") == []

    def test_skips_invalid_entries_gracefully(self, ws: str, tmp_path):
        records = [
            {
                "id": "ok-id",
                "type": "todo",
                "content": "ok",
                "source": "user",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "workspace_path": ws,
            },
            {"bad": "record"},
        ]
        (tmp_path / "todo_control.md").write_text(
            yaml.safe_dump(records, allow_unicode=True), encoding="utf-8"
        )
        result = read_todo_control(ws, "todo_control.md")
        assert len(result) == 1
        assert result[0].id == "ok-id"


# ---------------------------------------------------------------------------
# upsert_todo / find_todo / remove_todo
# ---------------------------------------------------------------------------


class TestUpsertFindRemove:
    def test_upsert_creates_entry(self, ws: str):
        entry = _make_todo(ws)
        upsert_todo(ws, "todo_control.md", entry)
        found = find_todo(ws, "todo_control.md", entry.id)
        assert found is not None
        assert found.id == entry.id
        assert found.content == "テストTODO"

    def test_upsert_updates_existing(self, ws: str):
        entry = _make_todo(ws)
        upsert_todo(ws, "todo_control.md", entry)
        updated = entry.model_copy(update={"content": "更新済みTODO"})
        upsert_todo(ws, "todo_control.md", updated)
        entries = read_todo_control(ws, "todo_control.md")
        assert len(entries) == 1
        assert entries[0].content == "更新済みTODO"

    def test_upsert_multiple_entries(self, ws: str):
        for i in range(3):
            upsert_todo(ws, "todo_control.md", _make_todo(ws, f"id-{i}"))
        assert len(read_todo_control(ws, "todo_control.md")) == 3

    def test_find_returns_none_for_missing_id(self, ws: str):
        upsert_todo(ws, "todo_control.md", _make_todo(ws))
        assert find_todo(ws, "todo_control.md", "nonexistent-id") is None

    def test_remove_returns_true_when_found(self, ws: str):
        entry = _make_todo(ws)
        upsert_todo(ws, "todo_control.md", entry)
        assert remove_todo(ws, "todo_control.md", entry.id) is True
        assert find_todo(ws, "todo_control.md", entry.id) is None

    def test_remove_returns_false_when_not_found(self, ws: str):
        assert remove_todo(ws, "todo_control.md", "nonexistent") is False

    def test_remove_leaves_other_entries(self, ws: str):
        upsert_todo(ws, "todo_control.md", _make_todo(ws, "id-a"))
        upsert_todo(ws, "todo_control.md", _make_todo(ws, "id-b"))
        remove_todo(ws, "todo_control.md", "id-a")
        remaining = read_todo_control(ws, "todo_control.md")
        assert len(remaining) == 1
        assert remaining[0].id == "id-b"


# ---------------------------------------------------------------------------
# アトミック書き込み（tmp ファイルが残らないこと）
# ---------------------------------------------------------------------------


def test_write_does_not_leave_tmp_file(ws: str, tmp_path):
    entry = _make_todo(ws)
    write_todo_control(ws, "todo_control.md", [entry])
    assert not (tmp_path / "todo_control.tmp").exists()
    assert (tmp_path / "todo_control.md").exists()


# ---------------------------------------------------------------------------
# migrate エンドポイント
# ---------------------------------------------------------------------------


def _create(client: TestClient, entry_type: str, content: str, source: str = "user", **kwargs):
    payload = {"type": entry_type, "content": content, "source": source, **kwargs}
    resp = client.post("/api/entries", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


class TestMigrateTodosToControl:
    def test_migrates_active_todos(self, client: TestClient, tmp_workspace):
        # 旧方式で articles/ に active todo を直接書き込む
        from src.storage.entry_writer import write_entry
        from src.config import config

        entry = _make_todo(str(tmp_workspace))
        write_entry(str(tmp_workspace), config.workspace.dirs.articles, entry)

        resp = client.post("/api/entries/migrate-todos-to-control")
        assert resp.status_code == 200
        data = resp.json()
        assert data["migrated"] == 1
        assert data["skipped"] == 0

        # articles/ から削除されていること
        assert not (tmp_workspace / "articles" / f"{entry.id}.md").exists()
        # todo_control.md に存在すること
        found = find_todo(str(tmp_workspace), config.workspace.dirs.todo_control, entry.id)
        assert found is not None

    def test_skips_non_active_todo_entries(self, client: TestClient, tmp_workspace):
        # completed todo は articles/ に残ったままにする（create_entry で todo_done は articles/ へ）
        _create(client, "todo_done", "完了済みタスク")
        _create(client, "diary", "日記エントリ")

        resp = client.post("/api/entries/migrate-todos-to-control")
        assert resp.status_code == 200
        data = resp.json()
        assert data["migrated"] == 0
        assert data["skipped"] == 2

    def test_migrated_todo_appears_on_timeline(self, client: TestClient, tmp_workspace):
        from src.storage.entry_writer import write_entry
        from src.config import config

        entry = _make_todo(str(tmp_workspace))
        write_entry(str(tmp_workspace), config.workspace.dirs.articles, entry)

        client.post("/api/entries/migrate-todos-to-control")

        resp = client.get("/api/timeline")
        todo_ids = {e["id"] for e in resp.json().get("todo_entries", [])}
        assert entry.id in todo_ids
