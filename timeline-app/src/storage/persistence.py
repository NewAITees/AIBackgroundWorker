"""Entry の永続化（articles/ + daily/ への一括書き込み）。"""

from __future__ import annotations

from ..config import config
from ..models.entry import Entry
from .daily_writer import upsert_entry_in_daily
from .entry_writer import write_entry


def persist_entry(workspace_path: str, entry: Entry) -> None:
    """entry を articles/ と daily/ の両方へ保存する。"""
    write_entry(workspace_path, config.workspace.dirs.articles, entry)
    upsert_entry_in_daily(workspace_path, config.workspace.dirs.daily, entry)
