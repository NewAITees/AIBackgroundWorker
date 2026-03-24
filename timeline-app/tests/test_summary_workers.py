"""hourly_summary_worker と daily_digest_worker の単体テスト。"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta

from src.config import config
from src.models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
from src.services.behavior_review import (
    build_daily_review_bundle,
    build_weekly_review_bundle,
    estimate_entry_traits,
)
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
    monkeypatch.setattr(worker, "_ensure_future_daily_files", lambda workspace_path: 3)
    monkeypatch.setattr(worker, "_ensure_recurring_todos", lambda workspace_path: 2)
    monkeypatch.setattr(
        "src.workers.daily_digest_worker.ai_control_service.is_paused", lambda: True
    )
    monkeypatch.setattr(
        "src.workers.daily_digest_worker.resolve_workspace_path",
        lambda: "/tmp/workspace",
    )

    assert worker._sync_once_blocking() == 0
    assert worker.get_status()["last_saved"] == 0
    assert worker.get_status()["last_future_daily_created"] == 3
    assert worker.get_status()["last_recurring_todo_created"] == 2


def test_daily_digest_worker_generates_for_unprocessed_dates(monkeypatch):
    worker = DailyDigestWorker()
    monkeypatch.setattr(worker, "_ensure_future_daily_files", lambda workspace_path: 2)
    monkeypatch.setattr(worker, "_ensure_recurring_todos", lambda workspace_path: 4)
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
    assert worker.get_status()["last_future_daily_created"] == 2
    assert worker.get_status()["last_recurring_todo_created"] == 4


def test_daily_digest_worker_ensures_future_daily_files(monkeypatch):
    worker = DailyDigestWorker()
    monkeypatch.setattr(config.lifelog, "future_daily_days_ahead", 2)

    fixed_now = datetime(2026, 3, 19, 12, 0, tzinfo=UTC)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    captured = {}

    def _ensure_future_daily_files(workspace_path, daily_dir, days_ahead, *, start_date=None):
        captured["workspace_path"] = workspace_path
        captured["daily_dir"] = daily_dir
        captured["days_ahead"] = days_ahead
        captured["start_date"] = start_date
        return ["a", "b"]

    monkeypatch.setattr("src.workers.daily_digest_worker.datetime", _FixedDatetime)
    monkeypatch.setattr(
        "src.workers.daily_digest_worker.ensure_future_daily_files", _ensure_future_daily_files
    )

    created = worker._ensure_future_daily_files("/tmp/workspace")
    assert created == 2
    assert captured == {
        "workspace_path": "/tmp/workspace",
        "daily_dir": config.workspace.dirs.daily,
        "days_ahead": 2,
        "start_date": date(2026, 3, 19),
    }
    assert worker.get_status()["last_future_daily_end_date"] == "2026-03-21"


def test_daily_digest_worker_ensures_recurring_todos(monkeypatch):
    worker = DailyDigestWorker()
    fixed_now = datetime(2026, 3, 19, 12, 0, tzinfo=UTC)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    source_entry = Entry(
        id="todo-1",
        type=EntryType.todo,
        title="薬を飲む",
        content="薬を飲む",
        timestamp=datetime(2026, 3, 18, 9, 0, tzinfo=UTC),
        status=EntryStatus.active,
        source=EntrySource.user,
        workspace_path="/tmp/workspace",
        meta=EntryMeta(
            recurring_enabled=True,
            recurring_rule="daily",
            recurring_interval=1,
            recurring_count=3,
            recurring_series_id="series-todo-1",
            recurring_sequence=1,
            recurring_scheduled_for="2026-03-18",
        ),
    )

    persisted = []

    def _persist_entry(workspace_path, entry):
        persisted.append(entry)

    monkeypatch.setattr("src.workers.daily_digest_worker.datetime", _FixedDatetime)
    monkeypatch.setattr(
        "src.workers.daily_digest_worker.read_entries", lambda *args, **kwargs: [source_entry]
    )
    monkeypatch.setattr("src.workers.daily_digest_worker.persist_entry", _persist_entry)

    created = worker._ensure_recurring_todos("/tmp/workspace")
    assert created == 1
    assert len(persisted) == 1
    assert [entry.meta.recurring_sequence for entry in persisted] == [2]
    assert [entry.meta.recurring_scheduled_for for entry in persisted] == ["2026-03-19"]
    assert all(entry.type == EntryType.todo for entry in persisted)
    assert all(entry.source == EntrySource.user for entry in persisted)


def test_daily_digest_worker_recurring_todos_skip_existing(monkeypatch):
    worker = DailyDigestWorker()
    fixed_now = datetime(2026, 3, 19, 12, 0, tzinfo=UTC)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    source_entry = Entry(
        id="todo-1",
        type=EntryType.todo,
        title="薬を飲む",
        content="薬を飲む",
        timestamp=datetime(2026, 3, 18, 9, 0, tzinfo=UTC),
        status=EntryStatus.active,
        source=EntrySource.user,
        workspace_path="/tmp/workspace",
        meta=EntryMeta(
            recurring_enabled=True,
            recurring_rule="daily",
            recurring_interval=1,
            recurring_count=3,
            recurring_series_id="series-todo-1",
            recurring_sequence=1,
            recurring_scheduled_for="2026-03-18",
        ),
    )
    existing_next = Entry(
        id="todo-2",
        type=EntryType.todo,
        title="薬を飲む",
        content="薬を飲む",
        timestamp=datetime(2026, 3, 19, 9, 0, tzinfo=UTC),
        status=EntryStatus.active,
        source=EntrySource.user,
        workspace_path="/tmp/workspace",
        meta=EntryMeta(
            recurring_enabled=True,
            recurring_rule="daily",
            recurring_interval=1,
            recurring_count=3,
            recurring_series_id="series-todo-1",
            recurring_sequence=2,
            recurring_scheduled_for="2026-03-19",
        ),
    )

    monkeypatch.setattr("src.workers.daily_digest_worker.datetime", _FixedDatetime)
    monkeypatch.setattr(
        "src.workers.daily_digest_worker.read_entries",
        lambda *args, **kwargs: [source_entry, existing_next],
    )
    monkeypatch.setattr(
        "src.workers.daily_digest_worker.persist_entry",
        lambda workspace_path, entry: (_ for _ in ()).throw(
            AssertionError("persist_entry should not run")
        ),
    )

    assert worker._ensure_recurring_todos("/tmp/workspace") == 0


def test_daily_digest_worker_next_recurring_date_for_custom_weekdays():
    worker = DailyDigestWorker()
    meta = EntryMeta(
        recurring_enabled=True,
        recurring_rule="custom_weekdays",
        recurring_interval=1,
        recurring_weekdays=[0, 2, 4],
    )
    assert worker._next_recurring_date(date(2026, 3, 18), meta) == date(2026, 3, 20)


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


def test_estimate_entry_traits_returns_conscientiousness_signal():
    entry = Entry(
        id="todo-done-1",
        type=EntryType.todo_done,
        title="TODOを完了して整理した",
        content="計画どおりに進めてレビューを完了",
        timestamp=datetime(2026, 3, 18, 9, 0, tzinfo=UTC),
        status=EntryStatus.done,
        source=EntrySource.user,
        workspace_path="/tmp/workspace",
        meta=EntryMeta(),
    )

    traits, evidence = estimate_entry_traits(entry)
    assert traits["conscientiousness"] > 0
    assert evidence


def test_build_daily_review_bundle_separates_review_and_big_five():
    config.behavior.review_enabled = True
    config.behavior.big_five_enabled = True
    config.behavior.review_perspectives = ["今日の前進"]
    config.behavior.big_five_focus_traits = ["conscientiousness"]
    entry = Entry(
        id="diary-1",
        type=EntryType.diary,
        title="進捗を書いた",
        content="TODOを整理して完了した。少し不安もあった。",
        timestamp=datetime(2026, 3, 18, 20, 0, tzinfo=UTC),
        status=EntryStatus.active,
        source=EntrySource.user,
        workspace_path="/tmp/workspace",
        meta=EntryMeta(),
    )

    bundle = build_daily_review_bundle(
        "/tmp/workspace", date(2026, 3, 18), [entry], config.behavior
    )
    assert bundle.review_entry is not None
    assert bundle.action_entry is not None
    assert bundle.review_entry.meta.review_kind == "daily_review"
    assert bundle.action_entry.meta.review_kind == "improvement_action"
    assert bundle.tagged_entries[0].meta.traits


def test_build_daily_review_bundle_filters_non_user_entries():
    config.behavior.review_enabled = True
    config.behavior.big_five_enabled = True
    user_entry = Entry(
        id="diary-user",
        type=EntryType.diary,
        title="ユーザー日記",
        content="TODOを整理して完了した",
        timestamp=datetime(2026, 3, 18, 20, 0, tzinfo=UTC),
        status=EntryStatus.active,
        source=EntrySource.user,
        workspace_path="/tmp/workspace",
        meta=EntryMeta(),
    )
    ai_entry = Entry(
        id="diary-ai",
        type=EntryType.diary,
        title="AI日記",
        content="自動生成レビュー",
        timestamp=datetime(2026, 3, 18, 21, 0, tzinfo=UTC),
        status=EntryStatus.active,
        source=EntrySource.ai,
        workspace_path="/tmp/workspace",
        meta=EntryMeta(),
    )

    bundle = build_daily_review_bundle(
        "/tmp/workspace", date(2026, 3, 18), [user_entry, ai_entry], config.behavior
    )
    assert bundle.review_entry is not None
    assert "ユーザー日記" in bundle.review_entry.content
    assert "AI日記" not in bundle.review_entry.content


def test_build_weekly_review_bundle_respects_trait_targets():
    config.behavior.review_enabled = True
    config.behavior.big_five_enabled = True
    config.behavior.big_five_trait_targets = {
        "openness": "keep",
        "conscientiousness": "up",
        "extraversion": "up",
        "agreeableness": "keep",
        "neuroticism": "down",
    }
    entry = Entry(
        id="todo-done-weekly",
        type=EntryType.todo_done,
        title="レビュー完了",
        content="レビューを完了して少し不安もあった",
        timestamp=datetime(2026, 3, 24, 9, 0, tzinfo=UTC),
        status=EntryStatus.done,
        source=EntrySource.user,
        workspace_path="/tmp/workspace",
        meta=EntryMeta(),
    )
    bundle = build_weekly_review_bundle(
        "/tmp/workspace", [entry], date(2026, 3, 29), config.behavior
    )
    assert bundle.review_entry is not None
    assert bundle.review_entry.meta.review_kind == "weekly_review"
    assert "週次レビュー" in bundle.review_entry.title
