"""hourly_summary_worker と daily_digest_worker の単体テスト。"""

from __future__ import annotations

from datetime import UTC, date, datetime

from src.config import config
from src.models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
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

    assert worker._sync_once_blocking() == 4
    assert imported["workspace_path"] == workspace_path
    assert imported["ctx"] == "CTX"
    assert imported["start_hour"] == datetime(2026, 3, 19, 7, 0, tzinfo=UTC)
    assert imported["end_hour"] == datetime(2026, 3, 19, 9, 0, tzinfo=UTC)
    status = worker.get_status()
    assert status["last_generated"] == 4
    assert status["last_range_start"] == datetime(2026, 3, 19, 7, 0, tzinfo=UTC).isoformat()
    assert status["last_range_end"] == datetime(2026, 3, 19, 9, 0, tzinfo=UTC).isoformat()
    assert status["last_sync_at"] is not None


def test_daily_digest_worker_target_dates_respects_lookback(monkeypatch):
    worker = DailyDigestWorker()
    monkeypatch.setattr(config.lifelog, "daily_digest_lookback_days", 3)

    class _FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 3, 19)

    monkeypatch.setattr("src.workers.daily_digest_worker.date", _FixedDate)

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
        def _chat_with_tools(self, messages, tools):
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
