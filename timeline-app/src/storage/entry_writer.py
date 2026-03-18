"""articles/*.md への entry 保存処理。"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..models.entry import Entry
from .common import article_path, entry_to_record


def write_entry(workspace_path: str, articles_dir: str, entry: Entry) -> Path:
    path = article_path(workspace_path, articles_dir, entry.id)
    path.parent.mkdir(parents=True, exist_ok=True)

    metadata = entry_to_record(entry)
    content = metadata.pop("content")
    frontmatter = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip()
    path.write_text(f"---\n{frontmatter}\n---\n{content.rstrip()}\n", encoding="utf-8")
    return path
