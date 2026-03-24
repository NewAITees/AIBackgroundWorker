"""設定 API (/api/settings) のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.config import config
from src.routers import settings as settings_router
from src.services.worker_control_service import _WORKER_DEFAULTS, worker_control_service


@pytest.fixture(autouse=True)
def reset_worker_states():
    """各テスト前後に worker 状態をデフォルトに戻す。"""
    worker_control_service.update_all(dict(_WORKER_DEFAULTS))
    yield
    worker_control_service.update_all(dict(_WORKER_DEFAULTS))


@pytest.fixture(autouse=True)
def reset_personality():
    """各テスト前後に personality をリセットする。"""
    original = config.ai.personality
    yield
    config.ai.personality = original


@pytest.fixture(autouse=True)
def temp_settings_files(monkeypatch, tmp_path):
    rss_path = tmp_path / "rss_feeds.txt"
    rss_path.write_text("# test feeds\nhttps://example.com/feed.xml\n", encoding="utf-8")
    search_path = tmp_path / "search_queries.txt"
    search_path.write_text("# test queries\n生成AI 最新動向\n", encoding="utf-8")
    monkeypatch.setattr(settings_router, "_RSS_PATH", Path(rss_path))
    monkeypatch.setattr(settings_router, "_SEARCH_QUERIES_PATH", Path(search_path))
    yield


class TestSettingsGet:
    def test_returns_ai_section(self, client: TestClient):
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        ai = resp.json()["ai"]
        for key in ("ollama_base_url", "ollama_model", "timeout_seconds", "personality"):
            assert key in ai

    def test_returns_workers_section(self, client: TestClient):
        resp = client.get("/api/settings")
        workers = resp.json()["workers"]
        for key in (
            "activity",
            "browser",
            "info",
            "analysis",
            "hourly_summary",
            "daily_digest",
            "windows",
        ):
            assert key in workers

    def test_workers_default_all_true(self, client: TestClient):
        resp = client.get("/api/settings")
        workers = resp.json()["workers"]
        for wid, enabled in workers.items():
            assert enabled is True, f"{wid} should default to True"

    def test_returns_feeds_section(self, client: TestClient):
        resp = client.get("/api/settings")
        data = resp.json()
        assert "feeds" in data
        assert isinstance(data["feeds"], list)
        assert "search_queries" in data
        assert isinstance(data["search_queries"], list)


class TestSettingsPatchAi:
    def test_update_personality(self, client: TestClient):
        resp = client.patch("/api/settings/ai", json={"personality": "フレンドリーに話す"})
        assert resp.status_code == 200
        assert resp.json()["personality"] == "フレンドリーに話す"

    def test_clear_personality(self, client: TestClient):
        client.patch("/api/settings/ai", json={"personality": "一時設定"})
        resp = client.patch("/api/settings/ai", json={"personality": ""})
        assert resp.status_code == 200
        assert resp.json()["personality"] == ""

    def test_partial_update_does_not_reset_personality(self, client: TestClient):
        client.patch("/api/settings/ai", json={"personality": "冷静に"})
        resp = client.patch("/api/settings/ai", json={"timeout_seconds": 120})
        data = resp.json()
        assert data["timeout_seconds"] == 120
        assert data["personality"] == "冷静に"

    def test_response_includes_all_fields(self, client: TestClient):
        resp = client.patch("/api/settings/ai", json={"personality": "テスト"})
        data = resp.json()
        for key in ("ollama_base_url", "ollama_model", "timeout_seconds", "personality"):
            assert key in data

    def test_personality_reflected_in_get(self, client: TestClient):
        client.patch("/api/settings/ai", json={"personality": "元気よく"})
        resp = client.get("/api/settings")
        assert resp.json()["ai"]["personality"] == "元気よく"


class TestSettingsWorkers:
    def test_disable_worker(self, client: TestClient):
        resp = client.patch("/api/settings/workers", json={"workers": {"activity": False}})
        assert resp.status_code == 200
        assert resp.json()["workers"]["activity"] is False

    def test_reenable_worker(self, client: TestClient):
        client.patch("/api/settings/workers", json={"workers": {"browser": False}})
        resp = client.patch("/api/settings/workers", json={"workers": {"browser": True}})
        assert resp.json()["workers"]["browser"] is True

    def test_partial_update_leaves_others_unchanged(self, client: TestClient):
        client.patch("/api/settings/workers", json={"workers": {"activity": False}})
        resp = client.patch("/api/settings/workers", json={"workers": {"browser": False}})
        workers = resp.json()["workers"]
        assert workers["activity"] is False
        assert workers["browser"] is False
        assert workers["info"] is True  # 未指定は変化なし

    def test_worker_state_reflected_in_get(self, client: TestClient):
        client.patch("/api/settings/workers", json={"workers": {"windows": False}})
        resp = client.get("/api/settings")
        assert resp.json()["workers"]["windows"] is False


class TestSettingsFeeds:
    def test_add_feed(self, client: TestClient):
        resp = client.post("/api/settings/feeds", json={"url": "https://example.com/new.rss"})
        assert resp.status_code == 201
        assert "https://example.com/new.rss" in resp.json()["feeds"]

    def test_delete_feed(self, client: TestClient):
        resp = client.request(
            "DELETE", "/api/settings/feeds", json={"url": "https://example.com/feed.xml"}
        )
        assert resp.status_code == 200
        assert "https://example.com/feed.xml" not in resp.json()["feeds"]


class TestSettingsSearchQueries:
    def test_add_search_query(self, client: TestClient):
        resp = client.post("/api/settings/search-queries", json={"query": "AI エージェント 最新"})
        assert resp.status_code == 201
        assert "AI エージェント 最新" in resp.json()["search_queries"]

    def test_delete_search_query(self, client: TestClient):
        resp = client.request(
            "DELETE",
            "/api/settings/search-queries",
            json={"query": "生成AI 最新動向"},
        )
        assert resp.status_code == 200
        assert "生成AI 最新動向" not in resp.json()["search_queries"]


class TestSettingsPipeline:
    def test_pipeline_includes_info_use_ollama(self, client: TestClient):
        resp = client.get("/api/settings")
        assert "info_use_ollama" in resp.json()["pipeline"]

    def test_update_info_use_ollama(self, client: TestClient):
        resp = client.patch("/api/settings/pipeline", json={"info_use_ollama": False})
        assert resp.status_code == 200
        assert resp.json()["info_use_ollama"] is False
        assert config.lifelog.info_use_ollama is False
