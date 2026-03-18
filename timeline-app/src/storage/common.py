"""Markdown 保存まわりの共通ユーティリティ。"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml

from ..models.entry import Entry


def dump_yaml(data: dict) -> str:
    """UTF-8 前提で読みやすい YAML 文字列を返す。"""
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False).strip()


def entry_to_record(entry: Entry) -> dict:
    """Entry を YAML 保存用の dict に変換する。"""
    return entry.model_dump(mode="json")


def entry_to_daily_block(entry: Entry) -> str:
    """daily ファイルへ埋め込む fenced yaml ブロックを生成する。"""
    body = dump_yaml(entry_to_record(entry))
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
