"""daily/YYYY-MM-DD.md への entry 同期処理。"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from pathlib import Path

from ..models.entry import Entry
from .common import (
    backup_existing_file,
    daily_path,
    ensure_entry_summary,
    entry_to_daily_block,
    parse_yaml_block,
    restore_from_backup,
)

logger = logging.getLogger(__name__)


def build_daily_content(target_date: date) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    lines = [
        f"# {date_str}",
        "",
        "## メモ",
        "",
        "",
        "---",
        "",
    ]

    for hour in range(24):
        lines.extend([f"## {hour:02d}:00", "", ""])

    return "\n".join(lines)


def ensure_daily_file(workspace_path: str, daily_dir: str, target_date: date) -> Path:
    path = daily_path(workspace_path, daily_dir, target_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(build_daily_content(target_date), encoding="utf-8")
    return path


def ensure_future_daily_files(
    workspace_path: str,
    daily_dir: str,
    days_ahead: int,
    *,
    start_date: date | None = None,
) -> list[Path]:
    """今日から指定日数先までの daily ファイルを不足分だけ補充する。"""
    base_date = start_date or date.today()
    horizon = max(days_ahead, 0)
    created: list[Path] = []
    for offset in range(horizon + 1):
        target_date = base_date + timedelta(days=offset)
        path = daily_path(workspace_path, daily_dir, target_date)
        if path.exists():
            continue
        created.append(ensure_daily_file(workspace_path, daily_dir, target_date))
    return created


def _section_marker(entry: Entry) -> str:
    return f"## {entry.timestamp.strftime('%H')}:00"


def _replace_section(content: str, marker: str, section_body: str) -> str:
    pattern = re.compile(rf"(?ms)^{re.escape(marker)}\n(.*?)(?=^## \d{{2}}:00\n|\Z)")
    match = pattern.search(content)
    if not match:
        raise ValueError(f"daily ファイルに時間セクションがありません: {marker}")
    return f"{content[:match.start(1)]}{section_body}{content[match.end(1):]}"


def _remove_existing_block(section_body: str, entry_id: str) -> str:
    kept_blocks: list[str] = []
    for chunk in re.split(r"(?=```yaml\n)", section_body.strip()):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith("```yaml") and f"id: {entry_id}" in chunk:
            continue
        kept_blocks.append(chunk)
    return "\n\n".join(kept_blocks)


def upsert_entry_in_daily(workspace_path: str, daily_dir: str, entry: Entry) -> Path:
    entry = ensure_entry_summary(entry)
    path = ensure_daily_file(workspace_path, daily_dir, entry.timestamp.date())
    content = path.read_text(encoding="utf-8")
    marker = _section_marker(entry)

    section_pattern = re.compile(rf"(?ms)^{re.escape(marker)}\n(.*?)(?=^## \d{{2}}:00\n|\Z)")
    match = section_pattern.search(content)
    if not match:
        raise ValueError(f"daily ファイルに時間セクションがありません: {marker}")

    section_body = _remove_existing_block(match.group(1), entry.id)
    block = entry_to_daily_block(entry)
    new_section = f"\n{section_body}\n\n{block}\n\n" if section_body else f"\n{block}\n\n"
    updated = _replace_section(content, marker, new_section)
    backup_existing_file(path)
    path.write_text(updated, encoding="utf-8")

    # 書き込み後の検証
    if not path.read_text(encoding="utf-8").strip():
        if restore_from_backup(path):
            logger.error("upsert_entry_in_daily: 書き込み検証失敗、バックアップから復元しました: %s", path)
        raise RuntimeError(f"daily ファイルの書き込み後の検証に失敗しました: {path}")

    return path


def remove_entry_from_daily(workspace_path: str, daily_dir: str, entry: Entry) -> Path:
    path = ensure_daily_file(workspace_path, daily_dir, entry.timestamp.date())
    content = path.read_text(encoding="utf-8")
    marker = _section_marker(entry)
    section_pattern = re.compile(rf"(?ms)^{re.escape(marker)}\n(.*?)(?=^## \d{{2}}:00\n|\Z)")
    match = section_pattern.search(content)
    if not match:
        return path

    cleaned = _remove_existing_block(match.group(1), entry.id)
    new_section = f"\n{cleaned}\n\n" if cleaned else "\n"
    updated = _replace_section(content, marker, new_section)
    backup_existing_file(path)
    path.write_text(updated, encoding="utf-8")

    if not path.read_text(encoding="utf-8").strip():
        if restore_from_backup(path):
            logger.error("remove_entry_from_daily: 書き込み検証失敗、バックアップから復元しました: %s", path)
        raise RuntimeError(f"daily ファイルの書き込み後の検証に失敗しました: {path}")

    return path


def normalize_daily_file(workspace_path: str, daily_dir: str, target_date: date) -> Path:
    """既存 daily の YAML ブロックを summary 投影形式へ揃える。"""
    path = ensure_daily_file(workspace_path, daily_dir, target_date)
    content = path.read_text(encoding="utf-8")

    def replace_block(match: re.Match[str]) -> str:
        raw = parse_yaml_block(match.group(0))
        if "content" not in raw:
            raw["content"] = raw.get("summary") or ""
        entry = ensure_entry_summary(Entry.model_validate(raw))
        return entry_to_daily_block(entry)

    normalized = re.sub(r"(?ms)^```yaml\n.*?^```", replace_block, content)
    if normalized != content:
        backup_existing_file(path)
        path.write_text(normalized, encoding="utf-8")

        if not path.read_text(encoding="utf-8").strip():
            if restore_from_backup(path):
                logger.error("normalize_daily_file: 書き込み検証失敗、バックアップから復元しました: %s", path)
            raise RuntimeError(f"daily ファイルの書き込み後の検証に失敗しました: {path}")

    return path
