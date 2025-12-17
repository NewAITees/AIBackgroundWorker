"""
Brave browser history importer.

This module provides functionality to import history from Brave browser's SQLite database.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class BraveHistoryImporter:
    """
    Braveブラウザ履歴インポーター.

    BraveブラウザのSQLiteデータベースから履歴を読み取り、
    将来的にデータベースにインポートする機能を提供します。
    """

    def __init__(self) -> None:
        """初期化."""
        self.default_profile_paths = [
            # Windows環境（直接実行）
            Path.home()
            / "AppData"
            / "Local"
            / "BraveSoftware"
            / "Brave-Browser"
            / "User Data"
            / "Default",
            # WSL環境からWindowsにアクセス
            Path("/mnt/c/Users")
            / Path.home().name
            / "AppData"
            / "Local"
            / "BraveSoftware"
            / "Brave-Browser"
            / "User Data"
            / "Default",
            # Linux環境
            Path.home() / ".config" / "BraveSoftware" / "Brave-Browser" / "Default",
        ]

    def _find_brave_history(self, profile_path: Optional[Path] = None) -> Optional[Path]:
        """
        Braveブラウザの履歴ファイルを検索.

        Args:
            profile_path: プロファイルパス（指定された場合）

        Returns:
            履歴ファイルのパス、見つからない場合はNone
        """
        if profile_path:
            history_path = Path(profile_path) / "History"
            if history_path.exists():
                return history_path
            return None

        # デフォルトパスから検索
        for profile_path in self.default_profile_paths:
            history_path = profile_path / "History"
            if history_path.exists():
                logger.info(f"Found Brave history at: {history_path}")
                return history_path

        logger.warning("Brave history file not found")
        return None

    def import_history(
        self, profile_path: Optional[Path] = None, limit: Optional[int] = None
    ) -> int:
        """
        ブラウザ履歴をインポート.

        Args:
            profile_path: プロファイルパス（指定された場合）
            limit: インポート件数上限（指定された場合）

        Returns:
            インポートした履歴の件数

        Raises:
            FileNotFoundError: 履歴ファイルが見つからない場合
        """
        history_path = self._find_brave_history(profile_path)
        if not history_path:
            raise FileNotFoundError(
                "Brave history file not found. "
                "Please specify --profile-path or ensure Brave is installed."
            )

        # Braveブラウザが履歴ファイルをロックしている可能性があるため、
        # コピーを作成して読み取る
        import shutil
        import tempfile

        temp_history = None
        try:
            # 一時ファイルにコピー
            temp_dir = tempfile.mkdtemp()
            temp_history = Path(temp_dir) / "History"
            shutil.copy2(history_path, temp_history)

            # SQLiteデータベースから履歴を読み取り
            conn = sqlite3.connect(str(temp_history))
            conn.row_factory = sqlite3.Row

            query = """
                SELECT
                    url,
                    title,
                    visit_count,
                    last_visit_time,
                    typed_count
                FROM urls
                ORDER BY last_visit_time DESC
            """
            if limit:
                query += f" LIMIT {limit}"

            cursor = conn.execute(query)
            rows = cursor.fetchall()

            count = 0
            for row in rows:
                # ここで将来的にデータベースに保存する処理を実装
                # 現時点では、読み取った件数をカウントするだけ
                count += 1
                logger.debug(
                    f"History entry: {row['url']} - {row['title']} "
                    f"(visits: {row['visit_count']})"
                )

            conn.close()
            logger.info(f"Imported {count} history entries from Brave")
            return count

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                raise FileNotFoundError(
                    "Brave browser is currently running and has locked the history file. "
                    "Please close Brave browser and try again."
                )
            raise
        finally:
            # 一時ファイルを削除
            if temp_history and temp_history.exists():
                temp_history.unlink()
                if temp_history.parent.exists():
                    temp_history.parent.rmdir()
