"""Markdown 保存まわりの共通ユーティリティ。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import shutil

import yaml

from ..models.entry import Entry


def dump_yaml(data: dict) -> str:
    """UTF-8 前提で読みやすい YAML 文字列を返す。"""
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False).strip()


def entry_to_record(entry: Entry) -> dict:
    """Entry を YAML 保存用の dict に変換する。"""
    return entry.model_dump(mode="json")


def summarize_text(content: str, limit: int = 120) -> str:
    """タイムライン表示用の短い summary を作る。"""
    normalized = " ".join(content.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def ensure_entry_summary(entry: Entry) -> Entry:
    """summary が空なら content から補完した Entry を返す。"""
    if entry.summary:
        return entry
    return entry.model_copy(update={"summary": summarize_text(entry.content)})


def entry_to_daily_record(entry: Entry) -> dict:
    """daily へ投影する最小レコードを返す。"""
    normalized = ensure_entry_summary(entry)
    record = normalized.model_dump(mode="json")
    record.pop("content", None)
    return record


def entry_to_daily_block(entry: Entry) -> str:
    """daily ファイルへ埋め込む fenced yaml ブロックを生成する。"""
    body = dump_yaml(entry_to_daily_record(entry))
    return f"```yaml\n{body}\n```"


def parse_yaml_block(block: str) -> dict:
    """fenced yaml ブロックから dict を復元する。"""
    lines = block.strip().splitlines()
    if len(lines) < 3 or lines[0].strip() != "```yaml" or lines[-1].strip() != "```":
        raise ValueError("YAML ブロック形式が不正です")
    body = "\n".join(lines[1:-1])
    return yaml.safe_load(body) or {}


def article_path(workspace_path: str, articles_dir: str, entry_id: str) -> Path:
    return Path(workspace_path) / articles_dir / f"{entry_id}.md"


def daily_path(workspace_path: str, daily_dir: str, target_date: date) -> Path:
    return Path(workspace_path) / daily_dir / f"{target_date.isoformat()}.md"


def iter_dates(start: date, end: date) -> list[date]:
    dates: list[date] = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def backup_existing_file(path: Path) -> Path | None:
    """既存 Markdown の退避コピーを .timeline-backups 配下へ作る。"""
    if not path.exists():
        return None

    backup_root = path.parent / ".timeline-backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_root / f"{path.name}.{timestamp}.bak"
    shutil.copy2(path, backup_path)
    return backup_path
