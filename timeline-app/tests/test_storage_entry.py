"""storage/entry_writer.py + entry_reader.py のテスト"""

from datetime import datetime, timezone

import pytest

from src.models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
from src.storage.entry_reader import read_entry
from src.storage.entry_writer import write_entry


def make_entry(**kwargs) -> Entry:
    defaults = dict(
        id="2026-03-18T10:00:00+00:00-diary-abc123",
        type=EntryType.diary,
        title="テストタイトル",
        content="本文テキスト",
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


class TestWriteReadEntry:
    def test_roundtrip(self, tmp_path):
        entry = make_entry(workspace_path=str(tmp_path))
        write_entry(str(tmp_path), "articles", entry)

        restored = read_entry(str(tmp_path), "articles", entry.id)
        assert restored.id == entry.id
        assert restored.type == entry.type
        assert restored.title == entry.title
        assert restored.content == entry.content
        assert restored.status == entry.status

    def test_file_created(self, tmp_path):
        entry = make_entry(workspace_path=str(tmp_path))
        path = write_entry(str(tmp_path), "articles", entry)
        assert path.exists()
        assert path.name == f"{entry.id}.md"

    def test_frontmatter_format(self, tmp_path):
        entry = make_entry(workspace_path=str(tmp_path))
        path = write_entry(str(tmp_path), "articles", entry)
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "\n---\n" in text
        # content は frontmatter の外に出る
        assert "content:" not in text.split("---\n")[1]
        assert entry.content in text

    def test_content_not_in_frontmatter(self, tmp_path):
        entry = make_entry(content="ユニークな本文XYZ", workspace_path=str(tmp_path))
        path = write_entry(str(tmp_path), "articles", entry)
        text = path.read_text(encoding="utf-8")
        # frontmatter 部分（--- と --- の間）に content フィールドがないこと
        frontmatter_section = text.split("---\n")[1]
        assert "content:" not in frontmatter_section

    def test_overwrite_updates_content(self, tmp_path):
        entry = make_entry(workspace_path=str(tmp_path))
        write_entry(str(tmp_path), "articles", entry)
        updated = entry.model_copy(update={"content": "更新後の本文"})
        write_entry(str(tmp_path), "articles", updated)
        restored = read_entry(str(tmp_path), "articles", entry.id)
        assert restored.content == "更新後の本文"

    def test_read_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_entry(str(tmp_path), "articles", "nonexistent-id")

    def test_unicode_content(self, tmp_path):
        entry = make_entry(content="日本語テスト🎉", workspace_path=str(tmp_path))
        write_entry(str(tmp_path), "articles", entry)
        restored = read_entry(str(tmp_path), "articles", entry.id)
        assert restored.content == "日本語テスト🎉"
