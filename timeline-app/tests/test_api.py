"""API エンドポイントのテスト（FastAPI TestClient使用）"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.ai.ollama_client import OllamaChatResult


def _mock_ollama(reply: str = "テスト応答です。", candidates=None) -> OllamaChatResult:
    return OllamaChatResult(reply=reply, entry_candidates=candidates or [])


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
