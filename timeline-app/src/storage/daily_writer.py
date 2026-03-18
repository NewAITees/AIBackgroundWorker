"""daily/YYYY-MM-DD.md への entry 同期処理。"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from ..models.entry import Entry
from .common import backup_existing_file, daily_path, entry_to_daily_block


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
    return path
