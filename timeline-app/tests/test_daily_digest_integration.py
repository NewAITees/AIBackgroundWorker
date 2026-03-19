"""daily_digest_worker の統合テスト。

実 Ollama を使って diary から振り返りを生成し、
articles/ と daily/ にファイルが保存されることまで確認する。
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from src.ai.ollama_client import OllamaClient
from src.config import config
from src.models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
from src.routers import workspace as workspace_module
from src.storage.daily_reader import read_daily_entries
from src.storage.entry_reader import read_entry
from src.storage.persistence import persist_entry
from src.workers.daily_digest_worker import DailyDigestWorker


@pytest.mark.integration
def test_daily_digest_worker_generates_article_and_daily_projection(tmp_path):
    workspace_module._workspace.clear()
    (tmp_path / "daily").mkdir()
    (tmp_path / "articles").mkdir()
    workspace_module._workspace.update(
        {
            "opened": True,
            "path": str(tmp_path),
            "mode": "standalone",
            "subdirs": {"daily": True, "articles": True},
        }
    )

    target_date = date(2026, 3, 18)
    diary_entry = Entry(
        id="integration-diary-2026-03-18",
        type=EntryType.diary,
        title="統合テスト用日記",
        summary="timeline-app の統合テストを進めた",
        content=("今日は timeline-app の統合テストを進めた。" "worker と timeline の流れが少しずつ揃ってきて手応えがあった。"),
        timestamp=datetime(2026, 3, 18, 21, 15, tzinfo=UTC),
        status=EntryStatus.active,
        source=EntrySource.user,
        workspace_path=str(tmp_path),
        meta=EntryMeta(),
    )
    persist_entry(str(tmp_path), diary_entry)

    worker = DailyDigestWorker()
    client = OllamaClient(config.ai)

    saved = worker._generate_for_date(client, str(tmp_path), target_date)
    assert saved == 1

    entry_id = "daily-digest-2026-03-18"
    article = read_entry(str(tmp_path), config.workspace.dirs.articles, entry_id)
    assert article.type == EntryType.memo
    assert article.title
    assert article.content
    assert len(article.content) > 10

    daily_entries = read_daily_entries(str(tmp_path), config.workspace.dirs.daily, target_date)
    ids = {entry.id for entry in daily_entries}
    assert entry_id in ids

    daily_digest = next(entry for entry in daily_entries if entry.id == entry_id)
    assert daily_digest.summary or daily_digest.content

    article_path = Path(tmp_path) / config.workspace.dirs.articles / f"{entry_id}.md"
    daily_path = Path(tmp_path) / config.workspace.dirs.daily / f"{target_date.isoformat()}.md"
    assert article_path.exists()
    assert daily_path.exists()

    workspace_module._workspace.clear()
