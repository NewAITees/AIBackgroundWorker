"""storage/daily_writer.py + daily_reader.py のテスト"""

from datetime import datetime, timezone

from src.models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
from src.storage.daily_reader import read_daily_entries, read_timeline_entries
from src.storage.daily_writer import (
    build_daily_content,
    ensure_daily_file,
    normalize_daily_file,
    remove_entry_from_daily,
    upsert_entry_in_daily,
)


def make_entry(hour: int = 10, **kwargs) -> Entry:
    defaults = dict(
        id=f"2026-03-18T{hour:02d}:00:00+00:00-diary-abc{hour:02d}",
        type=EntryType.diary,
        title=f"{hour}時のエントリ",
        content=f"hour={hour}の内容",
        timestamp=datetime(2026, 3, 18, hour, 0, 0, tzinfo=timezone.utc),
        status=EntryStatus.active,
        source=EntrySource.user,
        workspace_path="/ws",
        links=[],
        related_ids=[],
        meta=EntryMeta(),
    )
    defaults.update(kwargs)
    return Entry(**defaults)


class TestBuildDailyContent:
    def test_has_date_header(self):
        from datetime import date

        content = build_daily_content(date(2026, 3, 18))
        assert content.startswith("# 2026-03-18")

    def test_has_24_hour_sections(self):
        from datetime import date

        content = build_daily_content(date(2026, 3, 18))
        for hour in range(24):
            assert f"## {hour:02d}:00" in content

    def test_has_memo_section(self):
        from datetime import date

        content = build_daily_content(date(2026, 3, 18))
        assert "## メモ" in content


class TestEnsureDailyFile:
    def test_creates_file_if_not_exists(self, tmp_path):
        from datetime import date

        path = ensure_daily_file(str(tmp_path), "daily", date(2026, 3, 18))
        assert path.exists()
        assert path.name == "2026-03-18.md"

    def test_does_not_overwrite_existing(self, tmp_path):
        from datetime import date

        daily_dir = tmp_path / "daily"
        daily_dir.mkdir()
        target = daily_dir / "2026-03-18.md"
        target.write_text("既存の内容", encoding="utf-8")
        ensure_daily_file(str(tmp_path), "daily", date(2026, 3, 18))
        assert target.read_text(encoding="utf-8") == "既存の内容"


class TestUpsertEntryInDaily:
    def test_entry_appears_in_daily(self, tmp_path):
        entry = make_entry(hour=10, workspace_path=str(tmp_path))
        upsert_entry_in_daily(str(tmp_path), "daily", entry)
        text = (tmp_path / "daily" / "2026-03-18.md").read_text(encoding="utf-8")
        assert entry.id in text

    def test_update_replaces_existing_block(self, tmp_path):
        entry = make_entry(hour=10, workspace_path=str(tmp_path))
        upsert_entry_in_daily(str(tmp_path), "daily", entry)
        updated = entry.model_copy(update={"content": "更新後の内容"})
        upsert_entry_in_daily(str(tmp_path), "daily", updated)
        text = (tmp_path / "daily" / "2026-03-18.md").read_text(encoding="utf-8")
        # 同じ id のブロックは1つだけ存在する
        assert text.count(entry.id) == 1
        assert "更新後の内容" in text

    def test_multiple_entries_in_same_section(self, tmp_path):
        entry_a = make_entry(hour=10, workspace_path=str(tmp_path))
        entry_b = make_entry(
            hour=10,
            workspace_path=str(tmp_path),
            id="2026-03-18T10:30:00+00:00-diary-zzz999",
            content="同じ時間帯の別エントリ",
        )
        upsert_entry_in_daily(str(tmp_path), "daily", entry_a)
        upsert_entry_in_daily(str(tmp_path), "daily", entry_b)
        text = (tmp_path / "daily" / "2026-03-18.md").read_text(encoding="utf-8")
        assert entry_a.id in text
        assert entry_b.id in text


class TestRemoveEntryFromDaily:
    def test_removes_entry(self, tmp_path):
        entry = make_entry(hour=10, workspace_path=str(tmp_path))
        upsert_entry_in_daily(str(tmp_path), "daily", entry)
        remove_entry_from_daily(str(tmp_path), "daily", entry)
        text = (tmp_path / "daily" / "2026-03-18.md").read_text(encoding="utf-8")
        assert entry.id not in text

    def test_noop_if_not_exists(self, tmp_path):
        entry = make_entry(hour=10, workspace_path=str(tmp_path))
        # daily ファイルを先に作っておくが entry は書かない
        ensure_daily_file(str(tmp_path), "daily", entry.timestamp.date())
        remove_entry_from_daily(str(tmp_path), "daily", entry)  # 例外が出ないこと


class TestReadDailyEntries:
    def test_reads_written_entry(self, tmp_path):
        from datetime import date

        entry = make_entry(hour=10, workspace_path=str(tmp_path))
        upsert_entry_in_daily(str(tmp_path), "daily", entry)
        entries = read_daily_entries(str(tmp_path), "daily", date(2026, 3, 18))
        assert any(e.id == entry.id for e in entries)

    def test_returns_empty_for_missing_file(self, tmp_path):
        from datetime import date

        entries = read_daily_entries(str(tmp_path), "daily", date(2026, 3, 18))
        assert entries == []


class TestReadTimelineEntries:
    def test_filters_by_time_range(self, tmp_path):
        entry_in = make_entry(hour=10, workspace_path=str(tmp_path))
        entry_out = make_entry(
            hour=22,
            workspace_path=str(tmp_path),
            id="2026-03-18T22:00:00+00:00-diary-out999",
            content="範囲外",
        )
        upsert_entry_in_daily(str(tmp_path), "daily", entry_in)
        upsert_entry_in_daily(str(tmp_path), "daily", entry_out)

        start = datetime(2026, 3, 18, 9, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 18, 11, 0, 0, tzinfo=timezone.utc)
        entries = read_timeline_entries(str(tmp_path), "daily", start, end)

        ids = [e.id for e in entries]
        assert entry_in.id in ids
        assert entry_out.id not in ids

    def test_spans_multiple_days(self, tmp_path):
        entry_day1 = make_entry(hour=23, workspace_path=str(tmp_path))
        entry_day2 = make_entry(
            hour=1,
            workspace_path=str(tmp_path),
            id="2026-03-19T01:00:00+00:00-diary-day2",
            timestamp=datetime(2026, 3, 19, 1, 0, 0, tzinfo=timezone.utc),
            content="翌日エントリ",
        )
        upsert_entry_in_daily(str(tmp_path), "daily", entry_day1)
        upsert_entry_in_daily(str(tmp_path), "daily", entry_day2)

        start = datetime(2026, 3, 18, 22, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 19, 2, 0, 0, tzinfo=timezone.utc)
        entries = read_timeline_entries(str(tmp_path), "daily", start, end)

        ids = [e.id for e in entries]
        assert entry_day1.id in ids
        assert entry_day2.id in ids

    def test_content_filled_from_summary_when_missing(self, tmp_path):
        """daily YAML に content がない場合、summary から補完されること（critical bug fix）"""
        from datetime import date

        from src.storage.common import daily_path

        ensure_daily_file(str(tmp_path), "daily", date(2026, 3, 18))
        path = daily_path(str(tmp_path), "daily", date(2026, 3, 18))
        # content なし・summary あり の YAML ブロックを手書きで挿入
        yaml_block = (
            "```yaml\n"
            "id: test-no-content\n"
            "type: diary\n"
            "title: テスト\n"
            "summary: サマリーのみ\n"
            "timestamp: '2026-03-18T10:00:00+00:00'\n"
            "status: active\n"
            "source: user\n"
            "workspace_path: /ws\n"
            "links: []\n"
            "related_ids: []\n"
            "meta: {}\n"
            "```\n"
        )
        raw = path.read_text(encoding="utf-8")
        raw = raw.replace("## 10:00\n\n", f"## 10:00\n\n{yaml_block}\n")
        path.write_text(raw, encoding="utf-8")

        entries = read_daily_entries(str(tmp_path), "daily", date(2026, 3, 18))
        found = next((e for e in entries if e.id == "test-no-content"), None)
        assert found is not None
        assert found.content == "サマリーのみ"

    def test_results_sorted_by_timestamp(self, tmp_path):
        entries_to_write = [make_entry(hour=h, workspace_path=str(tmp_path)) for h in [14, 10, 12]]

        for e in entries_to_write:
            upsert_entry_in_daily(str(tmp_path), "daily", e)

        start = datetime(2026, 3, 18, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 18, 23, 59, 59, tzinfo=timezone.utc)
        results = read_timeline_entries(str(tmp_path), "daily", start, end)
        timestamps = [e.timestamp for e in results]
        assert timestamps == sorted(timestamps)


class TestNormalizeDailyFile:
    def test_removes_content_from_old_format_blocks(self, tmp_path):
        """content を含む旧フォーマットのブロックが summary 投影形式へ変換されること"""
        from datetime import date

        from src.storage.common import daily_path

        ensure_daily_file(str(tmp_path), "daily", date(2026, 3, 18))
        path = daily_path(str(tmp_path), "daily", date(2026, 3, 18))
        # content あり の古いフォーマットを手書きで挿入
        old_block = (
            "```yaml\n"
            "id: old-format-id\n"
            "type: diary\n"
            "summary: 短いサマリー\n"
            "content: 長い本文がここに入る\n"
            "timestamp: '2026-03-18T10:00:00+00:00'\n"
            "status: active\n"
            "source: user\n"
            "workspace_path: /ws\n"
            "links: []\n"
            "related_ids: []\n"
            "meta: {}\n"
            "```\n"
        )
        raw = path.read_text(encoding="utf-8")
        raw = raw.replace("## 10:00\n\n", f"## 10:00\n\n{old_block}\n")
        path.write_text(raw, encoding="utf-8")

        normalize_daily_file(str(tmp_path), "daily", date(2026, 3, 18))

        normalized = path.read_text(encoding="utf-8")
        assert "長い本文がここに入る" not in normalized
        assert "old-format-id" in normalized

    def test_idempotent(self, tmp_path):
        """normalize を2回かけても結果が変わらないこと"""
        from datetime import date

        entry = make_entry(hour=10, workspace_path=str(tmp_path))
        upsert_entry_in_daily(str(tmp_path), "daily", entry)

        normalize_daily_file(str(tmp_path), "daily", date(2026, 3, 18))
        path = tmp_path / "daily" / "2026-03-18.md"
        text_first = path.read_text(encoding="utf-8")

        normalize_daily_file(str(tmp_path), "daily", date(2026, 3, 18))
        text_second = path.read_text(encoding="utf-8")

        assert text_first == text_second
