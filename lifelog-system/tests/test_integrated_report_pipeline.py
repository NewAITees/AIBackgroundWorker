import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from src.browser_history.models import BrowserHistoryEntry
from src.browser_history.repository import BrowserHistoryRepository
from src.info_collector.data_aggregator import DailyReportDataAggregator
from src.info_collector.jobs.generate_integrated_report import generate_integrated_daily_report
from src.info_collector.repository import InfoCollectorRepository
from src.lifelog.database.db_manager import DatabaseManager


class StubLLM:
    """LLMレスポンスをモックするシンプルなクライアント."""

    def __init__(self, response: str = "stub report") -> None:
        self.response = response

    def generate(self, prompt: str, system: str | None = None, options=None) -> str:
        return self.response


def _setup_databases(tmp_path: Path) -> tuple[Path, Path, DatabaseManager, InfoCollectorRepository]:
    lifelog_db = tmp_path / "lifelog.db"
    info_db = tmp_path / "info.db"
    db_manager = DatabaseManager(str(lifelog_db))
    repo = InfoCollectorRepository(str(info_db))
    return lifelog_db, info_db, db_manager, repo


def test_generate_integrated_report_writes_file_and_db(tmp_path):
    lifelog_db, info_db, db_manager, repo = _setup_databases(tmp_path)

    target_date = "2024-01-01"
    now = datetime.fromisoformat(f"{target_date}T12:00:00")

    # lifelog intervals + events
    db_manager.bulk_insert_intervals(
        [
            {
                "start_ts": now,
                "end_ts": now + timedelta(minutes=10),
                "process_name": "editor.exe",
                "process_path_hash": "hash_editor",
                "window_hash": "win_hash",
                "domain": None,
                "is_idle": 0,
            }
        ]
    )
    db_manager.bulk_insert_events(
        [
            {
                "event_timestamp": now,
                "event_type": "warning",
                "severity": 70,
                "source": "linux_syslog",
                "category": "system",
                "event_id": 2001,
                "message": "disk space low",
                "message_hash": "hash",
                "raw_data_json": "{}",
                "process_name": "kernel",
                "user_name": None,
                "machine_name": "test-machine",
            }
        ]
    )

    # browser history
    browser_repo = BrowserHistoryRepository(info_db)
    browser_repo.add_entry(
        BrowserHistoryEntry(
            url="https://example.com",
            title="Example",
            visit_time=now,
        )
    )

    out_dir = tmp_path / "reports"
    stub_llm = StubLLM("stub content")

    report_path = generate_integrated_daily_report(
        lifelog_db_path=lifelog_db,
        info_db_path=info_db,
        output_dir=out_dir,
        date=target_date,
        detail_level="summary",
        llm_client_factory=lambda: stub_llm,
    )

    assert report_path is not None
    assert report_path.exists()
    assert "stub content" in report_path.read_text()

    saved_reports = repo.fetch_reports_by_date(target_date, category="integrated_daily")
    assert len(saved_reports) == 1
    assert saved_reports[0]["content"] == "stub content"


def test_unified_timeline_skips_invalid_entries(tmp_path):
    lifelog_db, info_db, db_manager, _ = _setup_databases(tmp_path)
    aggregator = DailyReportDataAggregator(lifelog_db, info_db)

    timeline = aggregator._build_unified_timeline(
        lifelog_data=[{"timestamp": "bad-ts", "process_name": "app", "window_hash": "wh"}],
        events=[
            {
                "event_timestamp": "2024-01-01T00:00:00",
                "event_type": "info",
                "severity": 10,
                "category": "system",
                "message": "ok",
            }
        ],
        browser_history=[],
        article_analyses=[],
        deep_research=[],
        date="2024-01-01",
    )

    # invalid lifelog timestamp should be skipped; event should remain
    assert len(timeline) == 1
    assert timeline[0]["source_type"] == "event"
