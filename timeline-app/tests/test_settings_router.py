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
def reset_vrm_model():
    """各テスト前後に VRM 設定をリセットする。"""
    original = config.vrm.model_filename
    yield
    config.vrm.model_filename = original


@pytest.fixture(autouse=True)
def reset_future_daily_days():
    original = config.lifelog.future_daily_days_ahead
    yield
    config.lifelog.future_daily_days_ahead = original


@pytest.fixture(autouse=True)
def reset_behavior_settings():
    original_review_enabled = config.behavior.review_enabled
    original_big_five_enabled = config.behavior.big_five_enabled
    original_daily_review_hour = config.behavior.daily_review_hour
    original_daily_review_minute = config.behavior.daily_review_minute
    original_weekly_review_weekday = config.behavior.weekly_review_weekday
    original_weekly_review_hour = config.behavior.weekly_review_hour
    original_weekly_review_minute = config.behavior.weekly_review_minute
    original_review_perspectives = list(config.behavior.review_perspectives)
    original_big_five_perspectives = list(config.behavior.big_five_perspectives)
    original_focus_traits = list(config.behavior.big_five_focus_traits)
    original_trait_targets = dict(config.behavior.big_five_trait_targets)
    yield
    config.behavior.review_enabled = original_review_enabled
    config.behavior.big_five_enabled = original_big_five_enabled
    config.behavior.daily_review_hour = original_daily_review_hour
    config.behavior.daily_review_minute = original_daily_review_minute
    config.behavior.weekly_review_weekday = original_weekly_review_weekday
    config.behavior.weekly_review_hour = original_weekly_review_hour
    config.behavior.weekly_review_minute = original_weekly_review_minute
    config.behavior.review_perspectives = original_review_perspectives
    config.behavior.big_five_perspectives = original_big_five_perspectives
    config.behavior.big_five_focus_traits = original_focus_traits
    config.behavior.big_five_trait_targets = original_trait_targets


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

    def test_returns_vrm_section(self, client: TestClient):
        resp = client.get("/api/settings")
        vrm = resp.json()["vrm"]
        assert "model_filename" in vrm
        assert "available_models" in vrm
        assert isinstance(vrm["available_models"], list)

    def test_returns_behavior_section(self, client: TestClient):
        resp = client.get("/api/settings")
        behavior = resp.json()["behavior"]
        for key in (
            "review_enabled",
            "big_five_enabled",
            "daily_review_hour",
            "daily_review_minute",
            "weekly_review_weekday",
            "weekly_review_hour",
            "weekly_review_minute",
            "review_perspectives",
            "big_five_perspectives",
            "big_five_focus_traits",
            "big_five_trait_targets",
        ):
            assert key in behavior


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
        assert "future_daily_days_ahead" in resp.json()["pipeline"]

    def test_update_info_use_ollama(self, client: TestClient):
        resp = client.patch("/api/settings/pipeline", json={"info_use_ollama": False})
        assert resp.status_code == 200
        assert resp.json()["info_use_ollama"] is False
        assert config.lifelog.info_use_ollama is False

    def test_update_future_daily_days_ahead(self, client: TestClient):
        resp = client.patch("/api/settings/pipeline", json={"future_daily_days_ahead": 14})
        assert resp.status_code == 200
        assert resp.json()["future_daily_days_ahead"] == 14
        assert config.lifelog.future_daily_days_ahead == 14


class TestSettingsBehavior:
    def test_update_behavior_settings(self, client: TestClient):
        resp = client.patch(
            "/api/settings/behavior",
            json={
                "review_enabled": True,
                "big_five_enabled": True,
                "daily_review_hour": 6,
                "daily_review_minute": 45,
                "weekly_review_weekday": 5,
                "weekly_review_hour": 10,
                "weekly_review_minute": 15,
                "review_perspectives": ["今日の前進", "集中と段取り"],
                "big_five_perspectives": ["どの行動がどの特性に出ていたか"],
                "big_five_focus_traits": ["conscientiousness", "extraversion", "invalid"],
                "big_five_trait_targets": {
                    "conscientiousness": "up",
                    "neuroticism": "down",
                    "bad": "up",
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["big_five_enabled"] is True
        assert data["daily_review_hour"] == 6
        assert data["daily_review_minute"] == 45
        assert data["weekly_review_weekday"] == 5
        assert data["weekly_review_hour"] == 10
        assert data["weekly_review_minute"] == 15
        assert data["review_perspectives"] == ["今日の前進", "集中と段取り"]
        assert data["big_five_focus_traits"] == ["conscientiousness", "extraversion"]
        assert data["big_five_trait_targets"] == {"conscientiousness": "up", "neuroticism": "down"}

    def test_behavior_reflected_in_get(self, client: TestClient):
        client.patch("/api/settings/behavior", json={"big_five_enabled": True})
        resp = client.get("/api/settings")
        assert resp.json()["behavior"]["big_five_enabled"] is True


class TestSettingsVrm:
    def test_update_vrm_model(self, client: TestClient):
        settings = client.get("/api/settings").json()
        available = settings["vrm"]["available_models"]
        if not available:
            pytest.skip("VRM model not available")

        resp = client.patch("/api/settings/vrm", json={"model_filename": available[0]})
        assert resp.status_code == 200
        assert resp.json()["model_filename"] == available[0]
        assert config.vrm.model_filename == available[0]

    def test_rejects_unknown_vrm_model(self, client: TestClient):
        resp = client.patch("/api/settings/vrm", json={"model_filename": "missing.vrm"})
        assert resp.status_code == 404
