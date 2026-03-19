"""articles/*.md への entry 保存処理。"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from ..models.entry import Entry
from .common import (
    article_path,
    backup_existing_file,
    ensure_entry_summary,
    entry_to_record,
    restore_from_backup,
)

logger = logging.getLogger(__name__)


def write_entry(workspace_path: str, articles_dir: str, entry: Entry) -> Path:
    entry = ensure_entry_summary(entry)
    path = article_path(workspace_path, articles_dir, entry.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_existing_file(path)

    metadata = entry_to_record(entry)
    content = metadata.pop("content")
    frontmatter = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip()
    path.write_text(f"---\n{frontmatter}\n---\n{content.rstrip()}\n", encoding="utf-8")

    # 書き込み後の検証（空ファイルや frontmatter 破損を検出）
    written = path.read_text(encoding="utf-8")
    if not written.startswith("---\n"):
        if restore_from_backup(path):
            logger.error("write_entry: 書き込み検証失敗、バックアップから復元しました: %s", path)
        raise RuntimeError(f"書き込み後の検証に失敗しました: {path}")

    return path
