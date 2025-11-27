#!/usr/bin/env python3
"""
Windows側のJSON Linesログを WSL側のSQLiteに統合するスクリプト.

Usage:
    uv run python scripts/lifelog/merge_windows_logs.py
    uv run python scripts/lifelog/merge_windows_logs.py --source /path/to/windows_foreground.jsonl
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parent.parent.parent
lifelog_system_path = project_root / "lifelog-system"
sys.path.insert(0, str(lifelog_system_path))

from src.lifelog.database.db_manager import DatabaseManager
from src.lifelog.utils.privacy import stable_hash

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_iso_datetime(dt_str: str) -> datetime:
    """
    ISO 8601形式の日時文字列をdatetimeに変換.

    Args:
        dt_str: ISO 8601形式の日時文字列

    Returns:
        datetime object
    """
    # Python 3.11+ では datetime.fromisoformat が "+09:00" を扱える
    return datetime.fromisoformat(dt_str)


def get_or_create_app(
    db: DatabaseManager, process_name: str, process_path: str, timestamp: datetime
) -> int:
    """
    アプリケーション情報を取得または作成.

    Args:
        db: データベースマネージャー
        process_name: プロセス名
        process_path: 実行ファイルパス
        timestamp: タイムスタンプ

    Returns:
        app_id
    """
    process_path_hash = stable_hash(process_path)

    # 既存レコード確認
    cursor = db._get_connection().execute(
        "SELECT app_id FROM apps WHERE process_name = ? AND process_path_hash = ?",
        (process_name, process_path_hash),
    )
    row = cursor.fetchone()

    if row:
        # last_seen更新
        db._get_connection().execute(
            "UPDATE apps SET last_seen = ? WHERE app_id = ?",
            (timestamp, row[0]),
        )
        return row[0]
    else:
        # 新規作成
        cursor = db._get_connection().execute(
            "INSERT INTO apps (process_name, process_path_hash, first_seen, last_seen) VALUES (?, ?, ?, ?)",
            (process_name, process_path_hash, timestamp, timestamp),
        )
        return cursor.lastrowid


def insert_activity_interval(
    db: DatabaseManager,
    start_ts: datetime,
    end_ts: datetime,
    app_id: int,
    window_title: str,
    is_idle: bool,
) -> None:
    """
    活動区間を挿入.

    Args:
        db: データベースマネージャー
        start_ts: 開始時刻
        end_ts: 終了時刻
        app_id: アプリID
        window_title: ウィンドウタイトル
        is_idle: アイドル状態
    """
    window_hash = stable_hash(window_title)

    # 重複チェック（同じ start_ts, app_id, window_hash のレコードがあればスキップ）
    cursor = db._get_connection().execute(
        "SELECT id FROM activity_intervals WHERE start_ts = ? AND app_id = ? AND window_hash = ?",
        (start_ts, app_id, window_hash),
    )
    if cursor.fetchone():
        logger.debug(f"Skipping duplicate record: {start_ts} - {app_id}")
        return

    db._get_connection().execute(
        "INSERT INTO activity_intervals (start_ts, end_ts, app_id, window_hash, is_idle) VALUES (?, ?, ?, ?, ?)",
        (start_ts, end_ts, app_id, window_hash, 1 if is_idle else 0),
    )


def merge_windows_logs(
    source_file: Path, db_path: Path, mark_processed: bool = True
) -> tuple[int, int]:
    """
    Windows側のJSON LinesログをSQLiteに統合.

    Args:
        source_file: Windows側のJSON Linesファイル
        db_path: SQLiteデータベースファイル
        mark_processed: 処理済みマーカーを作成するか

    Returns:
        (処理件数, スキップ件数)
    """
    if not source_file.exists():
        logger.error(f"Source file not found: {source_file}")
        return 0, 0

    db = DatabaseManager(str(db_path))

    processed_count = 0
    skipped_count = 0
    last_processed_line = 0

    # 処理済みマーカーファイル
    marker_file = source_file.with_suffix(".jsonl.processed")
    if marker_file.exists() and mark_processed:
        try:
            last_processed_line = int(marker_file.read_text().strip())
            logger.info(f"Resuming from line {last_processed_line + 1}")
        except ValueError:
            logger.warning("Invalid marker file, starting from beginning")

    try:
        with open(source_file, "r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, start=1):
                # 処理済みの行はスキップ
                if line_num <= last_processed_line:
                    skipped_count += 1
                    continue

                try:
                    record = json.loads(line.strip())

                    # 必須フィールドチェック
                    required_fields = ["start", "end", "process_name", "exe_path"]
                    if not all(field in record for field in required_fields):
                        logger.warning(f"Missing required fields in line {line_num}: {line.strip()}")
                        skipped_count += 1
                        continue

                    start_ts = parse_iso_datetime(record["start"])
                    end_ts = parse_iso_datetime(record["end"])
                    process_name = record["process_name"]
                    exe_path = record["exe_path"]
                    window_title = record.get("window_title", "")
                    is_idle = record.get("is_idle", False)  # デフォルトはFalse

                    # アプリID取得または作成
                    app_id = get_or_create_app(db, process_name, exe_path, start_ts)

                    # 活動区間挿入
                    insert_activity_interval(
                        db, start_ts, end_ts, app_id, window_title, is_idle
                    )

                    processed_count += 1

                    if processed_count % 100 == 0:
                        db._get_connection().commit()
                        logger.info(f"Processed {processed_count} records...")

                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in line {line_num}: {e}")
                    skipped_count += 1
                except Exception as e:
                    logger.error(f"Error processing line {line_num}: {e}")
                    skipped_count += 1

                # 処理済みマーカー更新
                if mark_processed and (line_num % 100 == 0):
                    marker_file.write_text(str(line_num))

        # 最終コミット
        db._get_connection().commit()

        # 最終マーカー更新
        if mark_processed:
            marker_file.write_text(str(line_num))

    finally:
        db.close()

    return processed_count, skipped_count


def main() -> None:
    """メインエントリーポイント."""
    parser = argparse.ArgumentParser(
        description="Merge Windows JSON Lines logs into SQLite database"
    )
    parser.add_argument(
        "--source",
        type=str,
        default=str(project_root / "lifelog-system" / "scripts" / "logs" / "windows_foreground.jsonl"),
        help="Source JSON Lines file (default: lifelog-system/scripts/logs/windows_foreground.jsonl)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(project_root / "lifelog-system" / "data" / "lifelog.db"),
        help="SQLite database file (default: lifelog-system/data/lifelog.db)",
    )
    parser.add_argument(
        "--no-marker",
        action="store_true",
        help="Don't use processed marker (reprocess all lines)",
    )

    args = parser.parse_args()

    source_file = Path(args.source)
    db_path = Path(args.db)

    logger.info(f"Merging Windows logs from {source_file} to {db_path}")

    processed, skipped = merge_windows_logs(
        source_file, db_path, mark_processed=not args.no_marker
    )

    logger.info(f"Merge completed: {processed} processed, {skipped} skipped")


if __name__ == "__main__":
    main()
