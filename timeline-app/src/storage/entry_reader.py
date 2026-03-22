"""articles/*.md から entry を復元する。"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from ..models.entry import Entry
from .common import article_path, ensure_entry_summary

_FRONTMATTER_RE = re.compile(r"(?ms)^---\n(?P<meta>.*?)\n---\n?(?P<body>.*)\Z")
_SAFE_ENTRY_ID_RE = re.compile(r"^[A-Za-z0-9_.+:\-]+$")


def read_entry(workspace_path: str, articles_dir: str, entry_id: str) -> Entry:
    if not _SAFE_ENTRY_ID_RE.match(entry_id):
        raise FileNotFoundError(f"無効な entry_id: {entry_id}")
    path = article_path(workspace_path, articles_dir, entry_id)
    return _read_entry_path(path, entry_id)


def read_entries(workspace_path: str, articles_dir: str) -> list[Entry]:
    articles_path = Path(workspace_path) / articles_dir
    if not articles_path.exists():
        return []

    entries: list[Entry] = []
    for path in sorted(articles_path.glob("*.md")):
        entries.append(_read_entry_path(path, path.stem))
    return entries


def _read_entry_path(path: Path, entry_id: str) -> Entry:
    raw = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        raise ValueError(f"frontmatter の形式が不正です: {path}")

    metadata = yaml.safe_load(match.group("meta")) or {}
    metadata["content"] = match.group("body").rstrip("\n")
    metadata["id"] = entry_id
    return ensure_entry_summary(Entry.model_validate(metadata))
