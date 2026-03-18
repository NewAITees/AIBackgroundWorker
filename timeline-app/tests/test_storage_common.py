"""storage/common.py のユニットテスト"""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
from src.storage.common import (
    backup_existing_file,
    entry_to_daily_block,
    entry_to_record,
    iter_dates,
    parse_yaml_block,
)


def make_entry(**kwargs) -> Entry:
    defaults = dict(
        id="2026-03-18T10:00:00+00:00-diary-abc123",
        type=EntryType.diary,
        title="テスト",
        content="今日はいい天気",
        timestamp=datetime(2026, 3, 18, 10, 0, 0, tzinfo=timezone.utc),
        status=EntryStatus.active,
        source=EntrySource.user,
        workspace_path="/ws",
        links=[],
        related_ids=[],
        meta=EntryMeta(),
    )
    defaults.update(kwargs)
    return Entry(**defaults)


class TestEntryToRecord:
    def test_contains_required_fields(self):
        entry = make_entry()
        record = entry_to_record(entry)
        assert record["id"] == entry.id
        assert record["type"] == "diary"
        assert record["content"] == "今日はいい天気"

    def test_timestamp_is_string(self):
        entry = make_entry()
        record = entry_to_record(entry)
        assert isinstance(record["timestamp"], str)


class TestEntryToDailyBlock:
    def test_fenced_yaml_format(self):
        entry = make_entry()
        block = entry_to_daily_block(entry)
        assert block.startswith("```yaml\n")
        assert block.endswith("\n```")

    def test_contains_entry_id(self):
        entry = make_entry()
        block = entry_to_daily_block(entry)
        assert entry.id in block


class TestParseYamlBlock:
    def test_roundtrip(self):
        entry = make_entry()
        block = entry_to_daily_block(entry)
        parsed = parse_yaml_block(block)
        assert parsed["id"] == entry.id
        assert parsed["type"] == "diary"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="YAML ブロック形式が不正です"):
            parse_yaml_block("not a yaml block")


class TestIterDates:
    def test_single_day(self):
        d = date(2026, 3, 18)
        assert iter_dates(d, d) == [d]

    def test_multiple_days(self):
        result = iter_dates(date(2026, 3, 18), date(2026, 3, 20))
        assert result == [date(2026, 3, 18), date(2026, 3, 19), date(2026, 3, 20)]

    def test_end_before_start_returns_empty(self):
        assert iter_dates(date(2026, 3, 20), date(2026, 3, 18)) == []


class TestBackupExistingFile:
    def test_returns_none_when_file_does_not_exist(self, tmp_path: Path):
        result = backup_existing_file(tmp_path / "nonexistent.md")
        assert result is None

    def test_creates_backup_copy(self, tmp_path: Path):
        original = tmp_path / "2026-03-18.md"
        original.write_text("original content", encoding="utf-8")
        backup = backup_existing_file(original)
        assert backup is not None
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == "original content"

    def test_backup_is_in_hidden_subdir(self, tmp_path: Path):
        original = tmp_path / "test.md"
        original.write_text("x", encoding="utf-8")
        backup = backup_existing_file(original)
        assert backup is not None
        assert backup.parent.name == ".timeline-backups"

    def test_original_is_not_deleted(self, tmp_path: Path):
        original = tmp_path / "test.md"
        original.write_text("content", encoding="utf-8")
        backup_existing_file(original)
        assert original.exists()
