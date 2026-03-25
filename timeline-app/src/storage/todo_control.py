"""todo_control.md の読み書き - active todo のカノニカルストア。

active todo はすべてここで管理する。完了・型変更時に articles/ + daily/ へ実体化される。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

from ..models.entry import Entry
from .common import ensure_entry_summary, entry_to_record

logger = logging.getLogger(__name__)


def todo_control_path(workspace_path: str, filename: str) -> Path:
    return Path(workspace_path) / filename


def read_todo_control(workspace_path: str, filename: str) -> list[Entry]:
    """todo_control.md から active todo 一覧を読み込む。"""
    path = todo_control_path(workspace_path, filename)
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    try:
        records = yaml.safe_load(raw) or []
    except yaml.YAMLError as exc:
        logger.warning("todo_control の YAML パース失敗: %s", exc)
        return []
    if not isinstance(records, list):
        logger.warning("todo_control の形式が不正です: %s", path)
        return []
    entries: list[Entry] = []
    for record in records:
        try:
            entries.append(ensure_entry_summary(Entry.model_validate(record)))
        except Exception as exc:
            logger.warning("todo_control エントリ読み込み失敗: %s", exc)
    return entries


def write_todo_control(workspace_path: str, filename: str, entries: list[Entry]) -> None:
    """todo_control.md に active todo 一覧を書き込む（全置換・アトミック）。"""
    path = todo_control_path(workspace_path, filename)
    records = [entry_to_record(ensure_entry_summary(e)) for e in entries]
    content = yaml.safe_dump(records, allow_unicode=True, sort_keys=False)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


def upsert_todo(workspace_path: str, filename: str, entry: Entry) -> None:
    """todo_control.md に entry を追加または更新する。"""
    entries = read_todo_control(workspace_path, filename)
    updated = [e for e in entries if e.id != entry.id]
    updated.append(entry)
    write_todo_control(workspace_path, filename, updated)


def remove_todo(workspace_path: str, filename: str, entry_id: str) -> bool:
    """todo_control.md から entry_id を削除する。見つかったら True を返す。"""
    entries = read_todo_control(workspace_path, filename)
    filtered = [e for e in entries if e.id != entry_id]
    if len(filtered) == len(entries):
        return False
    write_todo_control(workspace_path, filename, filtered)
    return True


def find_todo(workspace_path: str, filename: str, entry_id: str) -> Entry | None:
    """todo_control.md から entry_id を検索する。"""
    for entry in read_todo_control(workspace_path, filename):
        if entry.id == entry_id:
            return entry
    return None
