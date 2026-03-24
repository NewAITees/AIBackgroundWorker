"""週次レビュー API のテスト。"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.config import config
from src.models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
from src.storage.persistence import persist_entry


def test_weekly_review_separates_behavior_and_big_five(client: TestClient, tmp_workspace):
    config.behavior.review_enabled = True
    config.behavior.big_five_enabled = True
    config.behavior.daily_review_hour = 6
    config.behavior.daily_review_minute = 30
    config.behavior.weekly_review_weekday = 6
    config.behavior.weekly_review_hour = 9
    config.behavior.weekly_review_minute = 15
    config.behavior.review_perspectives = ["今日の前進", "詰まりやすかった点"]
    config.behavior.big_five_perspectives = ["どの行動がどの特性に出ていたか"]
    config.behavior.big_five_focus_traits = ["conscientiousness"]
    config.behavior.big_five_trait_targets = {
        "openness": "up",
        "conscientiousness": "up",
        "extraversion": "keep",
        "agreeableness": "up",
        "neuroticism": "down",
    }

    persist_entry(
        str(tmp_workspace),
        Entry(
            id="done-1",
            type=EntryType.todo_done,
            title="レビューを完了",
            content="計画を整理してレビューを完了した",
            timestamp=datetime(2026, 3, 24, 10, 0, tzinfo=UTC),
            status=EntryStatus.done,
            source=EntrySource.user,
            workspace_path=str(tmp_workspace),
            meta=EntryMeta(),
        ),
    )

    resp = client.get("/api/reviews/weekly?anchor_date=2026-03-25")
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_enabled"] is True
    assert data["big_five_enabled"] is True
    assert data["daily_review_time"] == "06:30"
    assert data["weekly_review_schedule"]["weekday"] == 6
    assert data["weekly_review_schedule"]["time"] == "09:15"
    assert data["big_five"]["focus_traits"] == ["conscientiousness"]
    assert data["big_five"]["trait_targets"]["neuroticism"] == "down"
    assert any(note["title"] == "今日の前進" for note in data["perspective_notes"])
    assert any(item["trait"] == "conscientiousness" for item in data["big_five"]["trait_notes"])
