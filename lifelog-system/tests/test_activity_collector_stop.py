"""
回帰テスト: ActivityCollector の start_collection → stop_collection 後に
ResourceWarning が出ないことを確認する。

検証手順:
  1. start_collection() でスレッドを起動
  2. 少し動かす（スレッドが DB 接続を作成するのを待つ）
  3. stop_collection() でスレッドを join して完全停止を待ち、DB 接続も閉じる
     ※ stop_collection() が db_manager.close() まで担う設計のため、
        呼び出し側は stop_collection() だけを呼べばよい
  4. gc.collect() で GC を強制し、ResourceWarning が出ないことを確認
"""

import gc
import time
import warnings
from unittest.mock import patch

from src.lifelog.collectors.activity_collector import ActivityCollector
from src.lifelog.database.db_manager import DatabaseManager

# スレッドのスリープをテスト時間内に収めるため、全インターバルを短くする
_TEST_CONFIG = {
    "collection": {
        "sampling_interval": 0.05,
        "idle_threshold": 60,
        "bulk_write": {
            "batch_size": 10,
            "timeout_seconds": 0.05,
            "max_queue_size": 1000,
        },
    },
    "health": {
        "snapshot_interval": 0.05,
    },
    "event_collection": {
        "enabled": False,
    },
    "slo": {},
}

_TEST_PRIVACY = {
    "privacy": {
        "exclude_processes": [],
        "sensitive_keywords": [],
    }
}

_MOCK_FOREGROUND = {
    "process_name": "test.exe",
    "window_hash": "abc123",
    "process_path_hash": "def456",
    "domain": None,
}


class TestActivityCollectorStop:
    """stop_collection() 後に ResourceWarning が出ないことを確認する回帰テスト."""

    def test_no_resource_warning_after_stop(self, tmp_path):
        """start → 短時間動作 → stop → gc で ResourceWarning ゼロを確認."""
        db_path = str(tmp_path / "test.db")
        db_manager = DatabaseManager(db_path)

        with (
            patch(
                "src.lifelog.collectors.activity_collector.get_foreground_info",
                return_value=_MOCK_FOREGROUND,
            ),
            patch(
                "src.lifelog.collectors.activity_collector.get_idle_seconds",
                return_value=0,
            ),
        ):
            collector = ActivityCollector(
                db_manager=db_manager,
                config=_TEST_CONFIG,
                privacy_config=_TEST_PRIVACY,
            )

            collector.start_collection()
            # スレッドが _get_connection() を呼んで接続を作るのに十分な時間を与える
            time.sleep(0.3)
            # join() で全スレッド終了を待ち、そのまま db_manager.close() まで行う
            collector.stop_collection()

        # ローカル参照を破棄して GC 対象にする
        # ※ db_manager.close() は stop_collection() 内で完了しているため不要
        del collector
        del db_manager

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            gc.collect()

        resource_warnings = [w for w in caught if issubclass(w.category, ResourceWarning)]
        assert (
            resource_warnings == []
        ), f"ResourceWarning が {len(resource_warnings)} 件検出されました:\n" + "\n".join(
            str(w.message) for w in resource_warnings
        )
