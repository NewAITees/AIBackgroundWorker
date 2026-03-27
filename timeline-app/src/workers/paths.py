"""workers 共通のパス解決・DB ユーティリティ。"""

from __future__ import annotations

import contextlib
import sqlite3
import sys
from pathlib import Path

from ..config import config, to_local_path


def repo_root() -> Path:
    """リポジトリルートを返す。"""
    return Path(__file__).resolve().parents[3]


def resolve_lifelog_path(raw_path: str) -> Path:
    """設定値のパスを絶対パスへ変換する。相対パスはリポジトリルート基準で解決する。"""
    path = Path(to_local_path(raw_path))
    if path.is_absolute():
        return path.resolve()
    return (repo_root() / path).resolve()


def lifelog_src() -> Path:
    """lifelog-system/src ディレクトリのパスを返す。"""
    return resolve_lifelog_path(config.lifelog.root_dir) / "src"


def ensure_lifelog_import_paths() -> None:
    """lifelog-system の両系統 import を解決できるよう sys.path を補正する。"""
    root_path = str(resolve_lifelog_path(config.lifelog.root_dir))
    src_path = str(Path(root_path) / "src")

    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    if root_path not in sys.path:
        sys.path.insert(0, root_path)

    import src as shared_src

    if src_path not in shared_src.__path__:
        shared_src.__path__.append(src_path)


def get_latest_sqlite_id(db_path: Path | str, table: str) -> int:
    """SQLite テーブルの MAX(id) を返す。レコードがなければ 0 を返す。"""
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}")  # noqa: S608
        row = cursor.fetchone()
        return int(row[0] or 0)
