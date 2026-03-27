"""API エンドポイントのテスト（FastAPI TestClient使用）"""

import asyncio
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.ai.ollama_client import OllamaChatResult


def _mock_ollama(reply: str = "テスト応答です。", candidates=None) -> OllamaChatResult:
    return OllamaChatResult(reply=reply, entry_candidates=candidates or [])


def _edit_mock(edited_content: str):
    from unittest.mock import MagicMock

    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "edit_entry_content",
                        "arguments": {
                            "edited_content": edited_content,
                        },
                    }
                }
            ],
        },
        "done": True,
    }
    return m


class TestHealth:
    def test_returns_ok(self, client: TestClient):
        with patch("src.routers.health.OllamaClient") as mock_cls:
            mock_cls.return_value.check_health.return_value = {"reachable": False}
            resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_includes_workspace_status(self, client: TestClient, tmp_workspace):
        with patch("src.routers.health.OllamaClient") as mock_cls:
            mock_cls.return_value.check_health.return_value = {"reachable": False}
            resp = client.get("/api/health")
        data = resp.json()
        assert "workspace" in data
        assert data["workspace"]["opened"] is True
        assert data["workspace"]["path"] == str(tmp_workspace)

    def test_includes_ollama_status(self, client: TestClient):
        ollama_status = {"reachable": True, "model": "qwen2.5:7b", "model_available": True}
        with patch("src.routers.health.OllamaClient") as mock_cls:
            mock_cls.return_value.check_health.return_value = ollama_status
            resp = client.get("/api/health")
        assert resp.json()["ollama"] == ollama_status

    def test_includes_worker_states_and_ai_paused(self, client: TestClient):
        ollama_status = {"reachable": True, "model": "qwen2.5:7b", "model_available": True}
        with (
            patch("src.routers.health.OllamaClient") as mock_cls,
            patch(
                "src.routers.health.ai_control_service.get_status", return_value={"paused": True}
            ),
            patch("src.routers.health.get_scheduler_status", return_value={"running": True}),
            patch("src.routers.health.activity_worker.get_status", return_value={"running": False}),
            patch("src.routers.health.browser_worker.get_status", return_value={"running": False}),
            patch("src.routers.health.info_worker.get_status", return_value={"running": False}),
            patch(
                "src.routers.health.analysis_pipeline_worker.get_status",
                return_value={"running": True, "last_analyzed": 3},
            ),
            patch(
                "src.routers.health.hourly_summary_worker.get_status",
                return_value={"running": False, "last_generated": 5},
            ),
            patch(
                "src.routers.health.daily_digest_worker.get_status",
                return_value={"running": False, "last_saved": 1},
            ),
        ):
            mock_cls.return_value.check_health.return_value = ollama_status
            resp = client.get("/api/health")
        data = resp.json()
        assert data["ollama"]["paused"] is True
        assert data["workers"]["analysis_pipeline"]["last_analyzed"] == 3
        assert data["workers"]["hourly_summary"]["last_generated"] == 5
        assert data["workers"]["daily_digest"]["last_saved"] == 1


class TestWorkspace:
    def test_get_workspace_opened(self, client: TestClient, tmp_workspace):
        resp = client.get("/api/workspace")
        assert resp.status_code == 200
        data = resp.json()
        assert data["opened"] is True
        assert data["path"] == str(tmp_workspace)

    def test_open_workspace_standalone(self, client: TestClient, tmp_workspace):
        resp = client.post("/api/workspace/open", json={"path": str(tmp_workspace)})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "standalone"

    def test_open_nonexistent_returns_404(self, client: TestClient):
        resp = client.post("/api/workspace/open", json={"path": "/nonexistent/path"})
        assert resp.status_code == 404

    def test_open_obsidian_vault(self, client: TestClient, tmp_workspace):
        (tmp_workspace / ".obsidian").mkdir()
        resp = client.post("/api/workspace/open", json={"path": str(tmp_workspace)})
        assert resp.json()["mode"] == "obsidian"


class TestVrm:
    def test_returns_vrm_metadata(self, client: TestClient):
        resp = client.get("/api/vrm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"].endswith(".vrm")
        assert data["url"].startswith("/api/vrm/model/")

    def test_serves_vrm_file(self, client: TestClient):
        meta = client.get("/api/vrm").json()
        resp = client.get(meta["url"])
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("model/gltf-binary")

    def test_vendor_static_is_served(self, client: TestClient):
        resp = client.get("/vendor/three/package.json")
        assert resp.status_code == 200


class TestEntries:
    def test_create_entry(self, client: TestClient):
        payload = {
            "type": "diary",
            "content": "今日はいい天気だった",
            "source": "user",
        }
        resp = client.post("/api/entries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "diary"
        assert data["content"] == "今日はいい天気だった"
        assert "id" in data

    def test_get_entry(self, client: TestClient):
        payload = {"type": "event", "content": "会議に出席した", "source": "user"}
        created = client.post("/api/entries", json=payload).json()
        resp = client.get(f"/api/entries/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_nonexistent_returns_404(self, client: TestClient):
        resp = client.get("/api/entries/nonexistent-id")
        assert resp.status_code == 404

    def test_patch_entry_content(self, client: TestClient):
        payload = {"type": "memo", "content": "元の内容", "source": "user"}
        created = client.post("/api/entries", json=payload).json()
        resp = client.patch(f"/api/entries/{created['id']}", json={"content": "更新後の内容"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "更新後の内容"

    def test_patch_nonexistent_returns_404(self, client: TestClient):
        resp = client.patch("/api/entries/nonexistent-id", json={"content": "x"})
        assert resp.status_code == 404

    def test_todo_default_timestamp_is_near_future(self, client: TestClient):
        """type=todo で timestamp 未指定のとき、保存時刻から約5分後が設定されること"""
        from datetime import datetime, timedelta, timezone

        before = datetime.now(timezone.utc)
        resp = client.post(
            "/api/entries", json={"type": "todo", "content": "やること", "source": "user"}
        )
        after = datetime.now(timezone.utc)
        assert resp.status_code == 201
        ts = datetime.fromisoformat(resp.json()["timestamp"])
        assert before + timedelta(minutes=4) <= ts <= after + timedelta(minutes=7)

    def test_create_without_workspace_returns_400(self, client: TestClient):
        from src.routers import workspace as workspace_module

        workspace_module._workspace.clear()
        try:
            resp = client.post(
                "/api/entries", json={"type": "memo", "content": "x", "source": "user"}
            )
            assert resp.status_code == 400
        finally:
            # conftest の tmp_workspace フィクスチャが cleanup するが念のため
            pass

    def test_ai_edit_creates_backup_and_returns_preview(self, client: TestClient, tmp_workspace):
        created = client.post(
            "/api/entries",
            json={"type": "memo", "content": "元の本文", "source": "user"},
        ).json()
        with patch("src.ai.ollama_client.requests.post", return_value=_edit_mock("編集後の本文")):
            resp = client.post(
                f"/api/entries/{created['id']}/ai_edit",
                json={"instruction": "読みやすくして"},
            )
        assert resp.status_code == 200
        assert resp.json()["edited_content"] == "編集後の本文"
        backup = tmp_workspace / "articles" / f"{created['id']}.bak.md"
        assert backup.exists()
        assert "元の本文" in backup.read_text(encoding="utf-8")

    def test_ai_edit_cancel_deletes_backup(self, client: TestClient, tmp_workspace):
        created = client.post(
            "/api/entries",
            json={"type": "memo", "content": "元の本文", "source": "user"},
        ).json()
        with patch("src.ai.ollama_client.requests.post", return_value=_edit_mock("編集後の本文")):
            client.post(
                f"/api/entries/{created['id']}/ai_edit",
                json={"instruction": "整形して"},
            )
        resp = client.delete(f"/api/entries/{created['id']}/ai_edit_backup")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        assert not (tmp_workspace / "articles" / f"{created['id']}.bak.md").exists()

    def test_append_message_appends_chat_transcript(self, client: TestClient):
        created = client.post(
            "/api/entries",
            json={"type": "chat_ai", "content": "最初の応答", "source": "ai"},
        ).json()
        resp = client.post(
            f"/api/entries/{created['id']}/append_message",
            json={"role": "user", "content": "追加の質問"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "最初の応答" in data["content"]
        assert "<!-- chat-message:user -->" in data["content"]
        assert "追加の質問" in data["content"]


class TestTimeline:
    def test_returns_empty_for_no_entries(self, client: TestClient):
        resp = client.get("/api/timeline")
        assert resp.status_code == 200
        assert resp.json()["entries"] == []

    def test_returns_created_entry(self, client: TestClient):
        payload = {"type": "diary", "content": "タイムラインに乗るか確認", "source": "user"}
        client.post("/api/entries", json=payload)
        resp = client.get("/api/timeline")
        assert resp.status_code == 200
        assert len(resp.json()["entries"]) >= 1


class TestAIControl:
    def test_ai_status(self, client: TestClient):
        with patch("src.routers.ai_control.ai_control_service.get_status") as get_status:
            get_status.return_value = {"paused": False, "paused_at": None, "resumed_at": None}
            resp = client.get("/api/ai/status")
        assert resp.status_code == 200
        assert resp.json()["paused"] is False

    def test_ai_pause(self, client: TestClient):
        with patch("src.routers.ai_control.ai_control_service.pause") as pause:
            pause.return_value = {"paused": True, "paused_at": "now", "resumed_at": None}
            resp = client.post("/api/ai/pause")
        assert resp.status_code == 200
        assert resp.json()["paused"] is True

    def test_ai_resume_triggers_catch_up(self, client: TestClient):
        scheduled: list[asyncio.coroutines] = []

        def _capture_task(coro):
            scheduled.append(coro)

            class _DummyTask:
                def cancel(self):
                    return None

            return _DummyTask()

        with (
            patch("src.routers.ai_control.ai_control_service.resume") as resume,
            patch("src.routers.ai_control.asyncio.create_task", side_effect=_capture_task),
        ):
            resume.return_value = {"paused": False, "paused_at": "before", "resumed_at": "now"}
            resp = client.post("/api/ai/resume")

        assert resp.status_code == 200
        assert resp.json()["paused"] is False
        assert len(scheduled) == 1
        scheduled[0].close()


def _chat_mock(reply: str, candidates: list | None = None):
    """Ollama /api/chat tool_calls 形式のモックを返す。"""
    from unittest.mock import MagicMock

    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "save_entry_candidates",
                        "arguments": {
                            "reply": reply,
                            "entry_candidates": candidates or [],
                        },
                    }
                }
            ],
        },
        "done": True,
    }
    return m


class TestChat:
    def test_returns_reply(self, client: TestClient):
        with patch("src.ai.ollama_client.requests.post", return_value=_chat_mock("了解です。")):
            resp = client.post("/api/chat", json={"content": "今日やることを整理したい"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["reply"] == "了解です。"
        assert "thread_id" in data
        assert "entry_candidates" in data

    def test_thread_id_preserved(self, client: TestClient):
        with patch("src.ai.ollama_client.requests.post", return_value=_chat_mock("続きです。")):
            resp = client.post("/api/chat", json={"content": "続き", "thread_id": "thread-test-001"})
        assert resp.json()["thread_id"] == "thread-test-001"

    def test_ollama_failure_returns_502(self, client: TestClient):
        import requests as req

        with patch("src.ai.ollama_client.requests.post", side_effect=req.RequestException("down")):
            resp = client.post("/api/chat", json={"content": "テスト"})
        assert resp.status_code == 502

    def test_chat_saves_transcript_markdown_entry(self, client: TestClient):
        with patch("src.ai.ollama_client.requests.post", return_value=_chat_mock("了解です。")):
            resp = client.post("/api/chat", json={"content": "今日やることを整理したい"})
        assert resp.status_code == 200

        timeline = client.get("/api/timeline").json()["entries"]
        chat_entries = [entry for entry in timeline if entry["type"] == "chat_ai"]
        assert chat_entries
        assert "<!-- chat-message:user -->" in chat_entries[-1]["content"]
        assert "<!-- chat-message:assistant -->" in chat_entries[-1]["content"]

    def test_chat_with_save_entry_false_does_not_persist_entry(self, client: TestClient):
        with patch("src.ai.ollama_client.requests.post", return_value=_chat_mock("了解です。")):
            resp = client.post(
                "/api/chat",
                json={"content": "続きです", "thread_id": "thread-x", "save_entry": False},
            )
        assert resp.status_code == 200
        timeline = client.get("/api/timeline").json()["entries"]
        assert [entry for entry in timeline if entry["type"] == "chat_ai"] == []

    def test_entry_candidates_returned(self, client: TestClient):
        candidates = [{"type": "todo", "title": "返信する", "content": "A社へ返信"}]
        with patch(
            "src.ai.ollama_client.requests.post",
            return_value=_chat_mock("記録しますね。", candidates),
        ):
            resp = client.post("/api/chat", json={"content": "A社へ返信しないといけない"})
        data = resp.json()
        assert len(data["entry_candidates"]) == 1
        assert data["entry_candidates"][0]["type"] == "todo"

    def test_invalid_candidate_type_is_filtered(self, client: TestClient):
        candidates = [{"type": "invalid_type", "content": "x"}]
        with patch(
            "src.ai.ollama_client.requests.post",
            return_value=_chat_mock("はい。", candidates),
        ):
            resp = client.post("/api/chat", json={"content": "テスト"})
        assert resp.json()["entry_candidates"] == []


class TestNewsFeedback:
    def test_get_feedback_stats(self, client: TestClient, monkeypatch):
        class _Repo:
            def get_feedback_stats(self):
                return {
                    "config": {"prior_alpha": 2.0},
                    "source": [{"name": "SourceA", "score": 0.8, "samples": 4.0}],
                    "category": [{"name": "AI", "score": 0.75, "samples": 3.0}],
                }

        monkeypatch.setattr("src.routers.news._load_repo", lambda: _Repo())

        resp = client.get("/api/news/feedback/stats")
        assert resp.status_code == 200
        assert resp.json()["source"][0]["name"] == "SourceA"
        assert resp.json()["category"][0]["name"] == "AI"

    def test_get_feedback_progress(self, client: TestClient, monkeypatch):
        class _Repo:
            def get_feedback_progress(self, recent_limit=10):
                assert recent_limit == 5
                return {
                    "overview": {"feedback_articles": 3, "analyzed_articles": 8},
                    "top_source": [{"name": "SourceA", "score": 0.8}],
                    "top_category": [{"name": "AI", "score": 0.7}],
                    "recent_events": [{"article_id": 1, "event_type": "feedback_positive"}],
                    "recent_analyses": [{"article_id": 2, "source_bonus": 0.04}],
                }

        monkeypatch.setattr("src.routers.news._load_repo", lambda: _Repo())

        resp = client.get("/api/news/feedback/progress?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overview"]["feedback_articles"] == 3
        assert data["recent_events"][0]["event_type"] == "feedback_positive"
        assert data["recent_analyses"][0]["source_bonus"] == 0.04

    def test_get_articles_includes_feedback_state(self, client: TestClient, monkeypatch):
        class _Repo:
            def get_articles_by_ids(self, article_ids):
                assert article_ids == [101, 102]
                return [
                    {"id": 101, "title": "A", "url": "https://example.com/a", "source_name": "src"},
                    {"id": 102, "title": "B", "url": "https://example.com/b", "source_name": "src"},
                ]

            def get_feedback_state_map(self, article_ids):
                return {
                    101: {
                        "sentiment": "positive",
                        "report_status": "done",
                        "report_entry_id": "report-9",
                    }
                }

            def get_article_analysis_map(self, article_ids):
                return {
                    101: {
                        "category": "AI",
                        "importance_score": 0.91,
                        "relevance_score": 0.84,
                        "llm_importance_score": 0.8,
                        "llm_relevance_score": 0.7,
                        "source_bonus": 0.07,
                        "category_bonus": 0.04,
                        "total_bonus": 0.11,
                        "importance_reason": "importance",
                        "relevance_reason": "relevance",
                    }
                }

        monkeypatch.setattr("src.routers.news._load_repo", lambda: _Repo())

        resp = client.get("/api/news/articles?ids=collected-info-101,collected-info-102")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["feedback"] == {
            "sentiment": "positive",
            "report_status": "done",
            "report_entry_id": "report-9",
        }
        assert data[0]["analysis"] == {
            "category": "AI",
            "importance_score": 0.91,
            "relevance_score": 0.84,
            "llm_importance_score": 0.8,
            "llm_relevance_score": 0.7,
            "source_bonus": 0.07,
            "category_bonus": 0.04,
            "total_bonus": 0.11,
            "importance_reason": "importance",
            "relevance_reason": "relevance",
        }
        assert data[1]["feedback"] == {
            "sentiment": None,
            "report_status": "none",
            "report_entry_id": None,
        }
        assert data[1]["analysis"] is None

    def test_post_feedback_toggles_exclusive_state(self, client: TestClient, monkeypatch):
        class _Repo:
            def toggle_feedback(self, article_id, feedback_type):
                assert article_id == 55
                assert feedback_type == "positive"
                return {
                    "sentiment": "positive",
                    "report_status": "none",
                    "report_entry_id": None,
                }

        monkeypatch.setattr("src.routers.news._load_repo", lambda: _Repo())

        resp = client.post("/api/news/articles/55/feedback", json={"type": "positive"})
        assert resp.status_code == 200
        assert resp.json()["feedback"] == {
            "sentiment": "positive",
            "report_status": "none",
            "report_entry_id": None,
        }

    def test_generate_report_queues_once_and_marks_positive(self, client: TestClient, monkeypatch):
        calls = {"forced": [], "task": None}

        class _Repo:
            def request_report(self, article_id):
                assert article_id == 77
                return True, {
                    "sentiment": "positive",
                    "report_status": "requested",
                    "report_entry_id": None,
                }

            def force_article_for_research(self, article_id):
                calls["forced"].append(article_id)

            def get_latest_report_id(self):
                return 12

        def _capture_task(article_id, last_report_id):
            calls["task"] = (article_id, last_report_id)

        monkeypatch.setattr("src.routers.news._load_repo", lambda: _Repo())
        monkeypatch.setattr("src.routers.news._run_pipeline_for_article", _capture_task)

        resp = client.post("/api/news/articles/77/generate_report")
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"
        assert resp.json()["feedback"] == {
            "sentiment": "positive",
            "report_status": "requested",
            "report_entry_id": None,
        }
        assert calls["forced"] == [77]
        assert calls["task"] == (77, 12)

    def test_generate_report_skips_when_already_done(self, client: TestClient, monkeypatch):
        class _Repo:
            def request_report(self, article_id):
                return False, {
                    "sentiment": "positive",
                    "report_status": "done",
                    "report_entry_id": "report-44",
                }

        monkeypatch.setattr("src.routers.news._load_repo", lambda: _Repo())

        resp = client.post("/api/news/articles/77/generate_report")
        assert resp.status_code == 200
        assert resp.json() == {
            "status": "already_requested",
            "article_id": 77,
            "feedback": {
                "sentiment": "positive",
                "report_status": "done",
                "report_entry_id": "report-44",
            },
        }
