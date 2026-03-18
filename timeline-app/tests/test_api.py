"""API エンドポイントのテスト（FastAPI TestClient使用）"""

from fastapi.testclient import TestClient


class TestHealth:
    def test_returns_ok(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


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


class TestChat:
    def test_returns_reply(self, client: TestClient):
        resp = client.post("/api/chat", json={"content": "今日やることを整理したい"})
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert "thread_id" in data
        assert "entry_candidates" in data

    def test_thread_id_preserved(self, client: TestClient):
        resp = client.post("/api/chat", json={"content": "続き", "thread_id": "thread-test-001"})
        assert resp.json()["thread_id"] == "thread-test-001"
