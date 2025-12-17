"""
Activity collector for lifelog-system.

イベント駆動 + バルク書き込みのハイブリッド実装
"""

import queue
import threading
import time
import logging
from datetime import datetime
from typing import Any, Optional

from ..database.db_manager import DatabaseManager
from .foreground_tracker import get_foreground_info
from .idle_detector import get_idle_seconds
from .health_monitor import HealthMonitor
from .event_collector import create_collector_for_platform_impl


logger = logging.getLogger(__name__)


class ActivityCollector:
    """
    活動収集クラス.

    イベント駆動でウィンドウ切替を検知し、
    メモリキューを経由してバルク書き込みを行う。
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        config: dict[str, Any],
        privacy_config: dict[str, Any],
    ) -> None:
        """
        初期化.

        Args:
            db_manager: データベースマネージャー
            config: 設定
            privacy_config: プライバシー設定
        """
        self.db = db_manager
        self.config = config
        self.privacy_config = privacy_config
        self.queue: queue.Queue = queue.Queue(
            maxsize=config.get("collection", {}).get("bulk_write", {}).get("max_queue_size", 1000)
        )
        self.current_interval: Optional[dict[str, Any]] = None
        self.health_monitor = HealthMonitor()
        self._running = False
        
        # イベント収集の初期化
        self.event_collector = None
        event_config = config.get("event_collection", {})
        if event_config.get("enabled", False):
            try:
                self.event_collector = create_collector_for_platform_impl(
                    config=event_config
                )
                logger.info("Event collection enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize event collector: {e}")

    def start_collection(self) -> None:
        """収集ループとバルク書き込みを並行実行."""
        self._running = True

        # 収集スレッド
        collect_thread = threading.Thread(target=self._collection_loop, daemon=True)
        collect_thread.start()

        # バルク書き込みスレッド
        write_thread = threading.Thread(target=self._bulk_write_loop, daemon=True)
        write_thread.start()

        # ヘルスモニタリングスレッド
        health_thread = threading.Thread(target=self._health_monitoring_loop, daemon=True)
        health_thread.start()

        # イベント収集スレッド
        if self.event_collector:
            event_thread = threading.Thread(target=self._event_collection_loop, daemon=True)
            event_thread.start()

        logger.info("Activity collection started")

    def stop_collection(self) -> None:
        """収集を停止."""
        self._running = False
        logger.info("Activity collection stopped")

    def _collection_loop(self) -> None:
        """イベント駆動 + 定期サンプリングのハイブリッド収集ループ."""
        last_foreground = None
        sampling_interval = self.config.get("collection", {}).get("sampling_interval", 12)
        idle_threshold = self.config.get("collection", {}).get("idle_threshold", 60)

        while self._running:
            try:
                now = datetime.now()
                idle_seconds = get_idle_seconds()
                current_foreground = get_foreground_info()

                if current_foreground is None:
                    time.sleep(sampling_interval)
                    continue

                # プライバシーチェック
                if self._should_exclude_process(current_foreground["process_name"]):
                    logger.debug(f"Excluding process: {current_foreground['process_name']}")
                    time.sleep(sampling_interval)
                    continue

                # イベント検知：ウィンドウ切替
                if current_foreground != last_foreground:
                    self._finalize_interval(now)
                    self._start_new_interval(current_foreground, now)
                    last_foreground = current_foreground

                # アイドル状態の判定
                is_idle = idle_seconds > idle_threshold
                if self.current_interval and self.current_interval["is_idle"] != is_idle:
                    self._finalize_interval(now)
                    self._start_new_interval(current_foreground, now, is_idle)

                # 定期サンプリング
                time.sleep(sampling_interval)

            except Exception as e:
                logger.error(f"Collection error: {e}", exc_info=True)
                time.sleep(5)

    def _should_exclude_process(self, process_name: str) -> bool:
        """プロセスを除外すべきか判定."""
        exclude_processes = self.privacy_config.get("privacy", {}).get("exclude_processes", [])
        sensitive_keywords = self.privacy_config.get("privacy", {}).get("sensitive_keywords", [])

        # 除外リストチェック
        if process_name.lower() in [p.lower() for p in exclude_processes]:
            return True

        # センシティブキーワードチェック
        process_lower = process_name.lower()
        for keyword in sensitive_keywords:
            if keyword.lower() in process_lower:
                return True

        return False

    def _start_new_interval(
        self, foreground_info: dict[str, Any], start_ts: datetime, is_idle: bool = False
    ) -> None:
        """新しい区間を開始."""
        self.current_interval = {
            "start_ts": start_ts,
            "foreground_info": foreground_info,
            "is_idle": is_idle,
        }

    def _finalize_interval(self, end_ts: datetime) -> None:
        """区間を確定してキューに追加."""
        if not self.current_interval:
            return

        interval = {
            **self.current_interval["foreground_info"],
            "start_ts": self.current_interval["start_ts"],
            "end_ts": end_ts,
            "is_idle": self.current_interval["is_idle"],
        }

        try:
            self.queue.put_nowait(interval)
            delay = (end_ts - self.current_interval["start_ts"]).total_seconds()
            self.health_monitor.record_collection_delay(delay)
        except queue.Full:
            logger.warning("Queue full, dropping interval")
            self.health_monitor.record_drop()

    def _bulk_write_loop(self) -> None:
        """キューから取り出してバルク書き込み."""
        batch: list[dict[str, Any]] = []
        last_write = datetime.now()
        batch_size = self.config.get("collection", {}).get("bulk_write", {}).get("batch_size", 10)
        timeout = self.config.get("collection", {}).get("bulk_write", {}).get("timeout_seconds", 3)

        while self._running:
            try:
                # タイムアウト付きで取得
                interval = self.queue.get(timeout=1.0)
                batch.append(interval)

                # 書き込み条件
                should_write = (
                    len(batch) >= batch_size
                    or (datetime.now() - last_write).total_seconds() > timeout
                )

                if should_write:
                    start_time = time.time()
                    self.db.bulk_insert_intervals(batch)
                    write_time_ms = (time.time() - start_time) * 1000
                    self.health_monitor.record_write_time(write_time_ms)

                    batch.clear()
                    last_write = datetime.now()

            except queue.Empty:
                # キューが空でもバッチがあれば書き込み
                if batch:
                    start_time = time.time()
                    self.db.bulk_insert_intervals(batch)
                    write_time_ms = (time.time() - start_time) * 1000
                    self.health_monitor.record_write_time(write_time_ms)

                    batch.clear()
                    last_write = datetime.now()

            except Exception as e:
                logger.error(f"Bulk write error: {e}", exc_info=True)
                time.sleep(5)

    def _health_monitoring_loop(self) -> None:
        """ヘルスモニタリングループ."""
        snapshot_interval = self.config.get("health", {}).get("snapshot_interval", 60)

        while self._running:
            try:
                time.sleep(snapshot_interval)

                # メトリクス収集
                metrics = self.health_monitor.get_metrics()
                self.db.save_health_snapshot(metrics)

                # SLOチェック
                slo_config = self.config.get("slo", {})
                slo_check = self.health_monitor.check_slo(slo_config)

                if not slo_check["healthy"]:
                    logger.warning(f"SLO violations detected: {slo_check['violations']}")

            except Exception as e:
                logger.error(f"Health monitoring error: {e}", exc_info=True)

    def _event_collection_loop(self) -> None:
        """イベント収集ループ."""
        if not self.event_collector:
            return

        event_config = self.config.get("event_collection", {})
        collection_interval = event_config.get("collection_interval", 300)
        last_collection_time = None
        privacy_config = event_config.get("privacy", {})

        while self._running:
            try:
                time.sleep(collection_interval)

                # イベント収集
                events = self.event_collector.collect_events(since=last_collection_time)

                if events:
                    # SystemEventをdictに変換
                    event_dicts = []
                    for event in events:
                        event_dicts.append({
                            "event_timestamp": event.event_timestamp,
                            "event_type": event.event_type,
                            "severity": event.severity,
                            "source": event.source,
                            "category": event.category,
                            "event_id": event.event_id,
                            "message": event.message,
                            "message_hash": event.message_hash,
                            "raw_data_json": event.raw_data_json,
                            "process_name": event.process_name,
                            "user_name": event.user_name,
                            "machine_name": event.machine_name,
                        })

                    # バルク挿入
                    self.db.bulk_insert_events(event_dicts)
                    logger.debug(f"Collected and saved {len(event_dicts)} events")
                    last_collection_time = datetime.now()

            except Exception as e:
                logger.error(f"Event collection error: {e}", exc_info=True)
                time.sleep(60)  # エラー時は1分待機
