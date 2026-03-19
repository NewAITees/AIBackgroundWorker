"""daily ファイルを読み込み timeline entry 一覧へ変換する。"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

from ..models.entry import Entry
from .common import daily_path, ensure_entry_summary, iter_dates, parse_yaml_block


def _as_utc(dt: datetime) -> datetime:
    """タイムゾーンなし datetime を UTC として扱い、aware に統一する。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


_SECTION_RE = re.compile(r"(?ms)^## (?P<hour>\d{2}:\d{2})\n(?P<body>.*?)(?=^## \d{2}:\d{2}\n|\Z)")
_BLOCK_RE = re.compile(r"(?ms)^```yaml\n.*?^```\n?")
_HIDDEN_ID_PREFIXES = ("lifelog-activity-", "collected-info-")
_HIDDEN_ID_SUFFIXES = ("-reports",)


def read_timeline_entries(
    workspace_path: str,
    daily_dir: str,
    start_at: datetime,
    end_at: datetime,
) -> list[Entry]:
    entries: list[Entry] = []
    for target_date in iter_dates(start_at.date(), end_at.date()):
        entries.extend(read_daily_entries(workspace_path, daily_dir, target_date))

    start_utc = _as_utc(start_at)
    end_utc = _as_utc(end_at)
    return sorted(
        [entry for entry in entries if start_utc <= _as_utc(entry.timestamp) <= end_utc],
        key=lambda entry: _as_utc(entry.timestamp),
    )


def read_daily_entries(workspace_path: str, daily_dir: str, target_date: date) -> list[Entry]:
    path = daily_path(workspace_path, daily_dir, target_date)
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8")
    entries: list[Entry] = []
    for section in _SECTION_RE.finditer(content):
        body = section.group("body")
        for block_match in _BLOCK_RE.finditer(body):
            raw = parse_yaml_block(block_match.group(0))
            if "content" not in raw:
                raw["content"] = raw.get("summary") or ""
            entry_id = str(raw.get("id", ""))
            if entry_id.startswith(_HIDDEN_ID_PREFIXES) or entry_id.endswith(_HIDDEN_ID_SUFFIXES):
                continue
            entry = Entry.model_validate(raw)
            entries.append(ensure_entry_summary(entry))
    return entries
