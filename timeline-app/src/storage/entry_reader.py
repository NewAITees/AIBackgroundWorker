"""articles/*.md から entry を復元する。"""

from __future__ import annotations

import re

import yaml

from ..models.entry import Entry
from .common import article_path, ensure_entry_summary

_FRONTMATTER_RE = re.compile(r"(?ms)^---\n(?P<meta>.*?)\n---\n?(?P<body>.*)\Z")


def read_entry(workspace_path: str, articles_dir: str, entry_id: str) -> Entry:
    path = article_path(workspace_path, articles_dir, entry_id)
    raw = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        raise ValueError(f"frontmatter の形式が不正です: {path}")

    metadata = yaml.safe_load(match.group("meta")) or {}
    metadata["content"] = match.group("body").rstrip("\n")
    metadata["id"] = entry_id
    return ensure_entry_summary(Entry.model_validate(metadata))
