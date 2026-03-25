"""
Linux syslog / journald イベントコレクター実装

journalctl を使用してシステムイベントを収集する。
Windows 環境では空リストを返す。
"""

import json
import logging
import platform
import subprocess
from datetime import datetime, timezone
from typing import List, Optional

from .event_classifier import EventClassifierImpl, _safe_text
from .event_collector_interface import EventClassifier, LinuxSyslogCollector, SystemEvent

logger = logging.getLogger(__name__)


class LinuxSyslogCollectorImpl(LinuxSyslogCollector):
    """Linux syslog/journaldを使用したイベント収集の実装"""

    def __init__(
        self,
        facility_filter: List[str] = None,
        priority_min: str = "warning",
        ignored_processes: Optional[List[str]] = None,
        classifier: EventClassifier = None,
        privacy_config: Optional[dict] = None,
    ):
        classifier = classifier or EventClassifierImpl()
        normalized_facility_filter = [
            _safe_text(v) for v in (facility_filter or ["kern", "user", "daemon"])
        ]
        normalized_priority_min = _safe_text(priority_min)
        if isinstance(priority_min, list):
            normalized_priority_min = _safe_text(priority_min[0] if priority_min else "warning")
        if not normalized_priority_min:
            normalized_priority_min = "warning"

        super().__init__(normalized_facility_filter, normalized_priority_min, classifier)
        self.privacy_config = privacy_config or {}
        self.ignored_processes = {
            _safe_text(v).lower() for v in (ignored_processes or ["tee"]) if _safe_text(v)
        }

    def _should_skip_raw_event(self, raw_event: dict) -> bool:
        process_name = _safe_text(raw_event.get("process_name", "")).lower()
        return bool(process_name and process_name in self.ignored_processes)

    def collect_events(
        self,
        since: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
    ) -> List[SystemEvent]:
        """
        Linux syslog/journaldからイベントを収集

        Args:
            since: この時刻以降のイベントを収集（Noneの場合は全期間）
            event_types: 収集するイベントタイプのリスト（Noneの場合はすべて）

        Returns:
            収集したイベントのリスト
        """
        if platform.system() == "Windows":
            logger.warning("Linux syslog collection is only available on Linux")
            return []

        events = []
        try:
            cmd = ["journalctl", "--no-pager", "--output=json"]

            if since:
                cmd.append(f"--since={since.isoformat()}")

            priority_map = {
                "debug": 7,
                "info": 6,
                "notice": 5,
                "warning": 4,
                "err": 3,
                "crit": 2,
                "alert": 1,
                "emerg": 0,
            }
            if self.priority_min in priority_map:
                min_priority = priority_map[self.priority_min]
                cmd.append(f"--priority=0..{min_priority}")

            if self.facility_filter:
                for facility in self.facility_filter:
                    cmd.append(f"--facility={facility}")

            cmd.append("--lines=1000")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.warning(f"journalctl command failed: {result.stderr}")
                return events

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    priority = item.get("PRIORITY")
                    if isinstance(priority, list):
                        priority = priority[0] if priority else None

                    raw_event = {
                        "timestamp": item.get("__REALTIME_TIMESTAMP"),
                        "level": priority,
                        "message": _safe_text(item.get("MESSAGE", "")),
                        "facility": _safe_text(item.get("SYSLOG_FACILITY")),
                        "process_name": _safe_text(item.get("_COMM")),
                        "user_name": _safe_text(item.get("_UID")),
                        "machine_name": _safe_text(item.get("_HOSTNAME", "")),
                    }

                    if self._should_skip_raw_event(raw_event):
                        continue

                    if raw_event["timestamp"]:
                        try:
                            ts_microseconds = int(raw_event["timestamp"]) / 1_000_000
                            raw_event["timestamp"] = datetime.fromtimestamp(
                                ts_microseconds, tz=timezone.utc
                            ).isoformat()
                        except (ValueError, TypeError):
                            raw_event["timestamp"] = datetime.now().isoformat()

                    event = SystemEvent.from_raw_event(
                        raw_event,
                        source="linux_syslog",
                        classifier=self.classifier,
                        privacy_config=self.privacy_config,
                    )
                    events.append(event)
                except json.JSONDecodeError:
                    continue

        except subprocess.TimeoutExpired:
            logger.warning("journalctl command timed out")
        except FileNotFoundError:
            logger.warning("journalctl command not found")
        except Exception as e:
            logger.error(f"Error collecting Linux events: {e}")

        return events
