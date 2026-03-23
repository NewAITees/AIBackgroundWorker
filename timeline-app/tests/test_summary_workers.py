"""hourly_summary_worker と daily_digest_worker の単体テスト。"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta

from src.config import config
from src.models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
from src.services.hourly_summary_importer import (
    get_local_timezone,
    summarize_news,
    summarize_search,
)
from src.workers.daily_digest_worker import DailyDigestWorker
from src.workers.hourly_summary_worker import HourlySummaryWorker


def test_hourly_summary_worker_skips_when_paused(monkeypatch):
    worker = HourlySummaryWorker()
    monkeypatch.setattr(
        "src.workers.hourly_summary_worker.ai_control_service.is_paused", lambda: True
    )
    monkeypatch.setattr(
        "src.workers.hourly_summary_worker.resolve_workspace_path",
        lambda: (_ for _ in ()).throw(AssertionError("workspace 解決は呼ばれない")),
    )

    assert worker._sync_once_blocking() == 0
    status = worker.get_status()
    assert status["last_generated"] == 0
    assert status["last_error"] is None


def test_hourly_summary_worker_imports_missing_hours(monkeypatch, tmp_path):
    worker = HourlySummaryWorker()
    workspace_path = str(tmp_path)

    monkeypatch.setattr(
        "src.workers.hourly_summary_worker.ai_control_service.is_paused", lambda: False
    )
    monkeypatch.setattr(
        "src.workers.hourly_summary_worker.resolve_workspace_path", lambda: workspace_path
    )
    monkeypatch.setattr(config.lifelog, "hourly_summary_lookback_hours", 3)

    fixed_now = datetime(2026, 3, 19, 10, 15, tzinfo=UTC)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    imported = {}

    def _resolve_context(path):
        imported["workspace_path"] = path
        return "CTX"

    def _import_missing_hours(ctx, start_hour, end_hour):
        imported["ctx"] = ctx
        imported["start_hour"] = start_hour
        imported["end_hour"] = end_hour
        return 4

    monkeypatch.setattr("src.workers.hourly_summary_worker.datetime", _FixedDatetime)
    monkeypatch.setattr("src.workers.hourly_summary_worker.resolve_context", _resolve_context)
    monkeypatch.setattr(
        "src.workers.hourly_summary_worker.import_missing_hours", _import_missing_hours
    )

    # コードと同じ方法で期待値を算出（ローカルタイムゾーン自動検出）
    expected_end = fixed_now.astimezone(get_local_timezone()).replace(
        minute=0, second=0, microsecond=0
    ) - timedelta(hours=1)
    expected_start = expected_end - timedelta(hours=2)  # lookback_hours=3 → -2h

    assert worker._sync_once_blocking() == 4
    assert imported["workspace_path"] == workspace_path
    assert imported["ctx"] == "CTX"
    assert imported["start_hour"] == expected_start
    assert imported["end_hour"] == expected_end
    status = worker.get_status()
    assert status["last_generated"] == 4
    assert status["last_range_start"] == expected_start.isoformat()
    assert status["last_range_end"] == expected_end.isoformat()
    assert status["last_sync_at"] is not None


def test_summarize_news_filters_out_search_and_limits_per_source():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE collected_info (
            id INTEGER PRIMARY KEY,
            source_type TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            content TEXT,
            snippet TEXT,
            published_at TEXT,
            fetched_at TEXT NOT NULL,
            source_name TEXT,
            metadata_json TEXT
        )
        """
    )
    rows = []
    base_time = "2026-03-23T13:{minute:02d}:00"
    for idx in range(6):
        rows.append(
            (
                idx + 1,
                "rss",
                f"RSS {idx + 1}",
                f"https://rss.example/{idx + 1}",
                None,
                f"rss snippet {idx + 1}",
                None,
                base_time.format(minute=idx),
                "Feed A",
                None,
            )
        )
    rows.append(
        (
            100,
            "search",
            "Search result",
            "https://search.example/1",
            None,
            "search snippet",
            None,
            "2026-03-23T13:30:00",
            "DuckDuckGo",
            None,
        )
    )
    conn.executemany(
        """
        INSERT INTO collected_info
        (id, source_type, title, url, content, snippet, published_at, fetched_at, source_name, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )

    entry = summarize_news(conn, date(2026, 3, 23), 22)
    assert entry is not None
    assert entry.type == EntryType.news
    assert len(entry.related_ids) == 5
    assert "### Feed A" in entry.content
    assert "DuckDuckGo" not in entry.content
    assert "RSS 1" not in entry.content


def test_summarize_search_uses_search_rows_only():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE collected_info (
            id INTEGER PRIMARY KEY,
            source_type TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            content TEXT,
            snippet TEXT,
            published_at TEXT,
            fetched_at TEXT NOT NULL,
            source_name TEXT,
            metadata_json TEXT
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO collected_info
        (id, source_type, title, url, content, snippet, published_at, fetched_at, source_name, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                1,
                "search",
                "Search 1",
                "https://search.example/1",
                None,
                "search snippet",
                None,
                "2026-03-23T13:00:00",
                "DuckDuckGo",
                None,
            ),
            (
                2,
                "rss",
                "RSS 1",
                "https://rss.example/1",
                None,
                "rss snippet",
                None,
                "2026-03-23T13:10:00",
                "Feed A",
                None,
            ),
        ],
    )

    entry = summarize_search(conn, date(2026, 3, 23), 22)
    assert entry is not None
    assert entry.type == EntryType.search
    assert entry.related_ids == ["collected-info-1"]
    assert "DuckDuckGo" in entry.content
    assert "Feed A" not in entry.content


def test_daily_digest_worker_target_dates_respects_lookback(monkeypatch):
    worker = DailyDigestWorker()
    monkeypatch.setattr(config.lifelog, "daily_digest_lookback_days", 3)

    # _target_dates は datetime.now(UTC).date() を使うので datetime をmonkeypatch する
    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 19, 12, 0, tzinfo=UTC)

    monkeypatch.setattr("src.workers.daily_digest_worker.datetime", _FixedDatetime)

    assert worker._target_dates() == [
        date(2026, 3, 16),
        date(2026, 3, 17),
        date(2026, 3, 18),
    ]


def test_daily_digest_worker_skips_when_paused(monkeypatch):
    worker = DailyDigestWorker()
    monkeypatch.setattr(
        "src.workers.daily_digest_worker.ai_control_service.is_paused", lambda: True
    )
    monkeypatch.setattr(
        "src.workers.daily_digest_worker.resolve_workspace_path",
        lambda: (_ for _ in ()).throw(AssertionError("workspace 解決は呼ばれない")),
    )

    assert worker._sync_once_blocking() == 0
    assert worker.get_status()["last_saved"] == 0


def test_daily_digest_worker_generates_for_unprocessed_dates(monkeypatch):
    worker = DailyDigestWorker()
    monkeypatch.setattr(
        "src.workers.daily_digest_worker.ai_control_service.is_paused", lambda: False
    )
    monkeypatch.setattr(
        "src.workers.daily_digest_worker.resolve_workspace_path", lambda: "/tmp/workspace"
    )
    monkeypatch.setattr(worker, "_target_dates", lambda: [date(2026, 3, 17), date(2026, 3, 18)])

    generated = []

    def _generate_for_date(client, workspace_path, target_date):
        generated.append((client, workspace_path, target_date))
        return 1 if target_date.day == 17 else 0

    monkeypatch.setattr(worker, "_generate_for_date", _generate_for_date)

    class _DummyClient:
        def __init__(self, ai_config):
            self.ai_config = ai_config

    monkeypatch.setattr("src.workers.daily_digest_worker.OllamaClient", _DummyClient)

    result = worker._sync_once_blocking()
    assert result == 1
    assert len(generated) == 2
    assert all(item[1] == "/tmp/workspace" for item in generated)
    assert worker.get_status()["last_target_date"] == "2026-03-18"
    assert worker.get_status()["last_saved"] == 1


def test_daily_digest_worker_generate_for_date_skips_if_entry_exists(monkeypatch):
    worker = DailyDigestWorker()
    existing = Entry(
        id="daily-digest-2026-03-18",
        type=EntryType.memo,
        title="existing",
        content="already there",
        timestamp=datetime(2026, 3, 18, 23, 50, tzinfo=UTC),
        status=EntryStatus.active,
        source=EntrySource.ai,
        workspace_path="/tmp/workspace",
        meta=EntryMeta(),
    )
    monkeypatch.setattr(
        "src.workers.daily_digest_worker.read_daily_entries", lambda *args, **kwargs: [existing]
    )

    assert worker._generate_for_date(object(), "/tmp/workspace", date(2026, 3, 18)) == 0


def test_daily_digest_worker_generate_for_date_persists_entry(monkeypatch):
    worker = DailyDigestWorker()
    diary = Entry(
        id="diary-1",
        type=EntryType.diary,
        title="日記",
        summary="summary",
        content="今日は進んだ",
        timestamp=datetime(2026, 3, 18, 20, 0, tzinfo=UTC),
        status=EntryStatus.active,
        source=EntrySource.user,
        workspace_path="/tmp/workspace",
        meta=EntryMeta(),
    )
    monkeypatch.setattr(
        "src.workers.daily_digest_worker.read_daily_entries", lambda *args, **kwargs: [diary]
    )

    persisted = {}

    def _persist_entry(workspace_path, entry):
        persisted["workspace_path"] = workspace_path
        persisted["entry"] = entry

    monkeypatch.setattr("src.workers.daily_digest_worker.persist_entry", _persist_entry)

    class _DummyClient:
        def _chat_with_tools(self, messages, tools, **kwargs):
            return ({"title": "振り返り", "content": "よく進めた。次もこの調子。"}, None)

    result = worker._generate_for_date(_DummyClient(), "/tmp/workspace", date(2026, 3, 18))
    assert result == 1
    assert persisted["workspace_path"] == "/tmp/workspace"
    entry = persisted["entry"]
    assert entry.id == "daily-digest-2026-03-18"
    assert entry.type == EntryType.memo
    assert entry.title == "振り返り"
    assert entry.content == "よく進めた。次もこの調子。"
    assert entry.timestamp == datetime(2026, 3, 18, 23, 50, tzinfo=UTC)
