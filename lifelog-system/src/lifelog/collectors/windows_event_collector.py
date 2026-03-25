"""
Windows EventLog イベントコレクター実装

Windows EventLog APIを使用してシステムイベントを収集する。
WSL/Linux 環境では空リストを返す。
"""

import json
import logging
import platform
import subprocess
from datetime import datetime
from typing import List, Optional

from .event_classifier import EventClassifierImpl
from .event_collector_interface import EventClassifier, SystemEvent, WindowsEventLogCollector

logger = logging.getLogger(__name__)


class WindowsEventLogCollectorImpl(WindowsEventLogCollector):
    """Windows EventLog APIを使用したイベント収集の実装"""

    def __init__(
        self,
        log_names: List[str] = None,
        classifier: EventClassifier = None,
        privacy_config: Optional[dict] = None,
    ):
        classifier = classifier or EventClassifierImpl()
        super().__init__(log_names, classifier)
        self.privacy_config = privacy_config or {}
        if platform.system() != "Windows":
            logger.warning("WindowsEventLogCollector is only available on Windows")

    def collect_events(
        self,
        since: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
    ) -> List[SystemEvent]:
        """
        Windows EventLogからイベントを収集

        Args:
            since: この時刻以降のイベントを収集（Noneの場合は全期間）
            event_types: 収集するイベントタイプのリスト（Noneの場合はすべて）

        Returns:
            収集したイベントのリスト
        """
        if platform.system() != "Windows":
            logger.warning("Windows EventLog collection is only available on Windows")
            return []

        events = []
        try:
            for log_name in self.log_names:
                events.extend(self._collect_from_log(log_name, since, event_types))
        except Exception as e:
            logger.error(f"Failed to collect Windows events: {e}")

        return events

    def _collect_from_log(
        self,
        log_name: str,
        since: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
    ) -> List[SystemEvent]:
        """特定のログからイベントを収集"""
        events = []

        try:
            if since:
                ps_cmd = f"""
                $since = [DateTime]::Parse('{since.isoformat()}')
                Get-WinEvent -LogName {log_name} -MaxEvents 1000 | Where-Object {{ $_.TimeCreated -ge $since }} | ForEach-Object {{
                    [PSCustomObject]@{{
                        TimeCreated = $_.TimeCreated.ToString('yyyy-MM-ddTHH:mm:ss')
                        Id = $_.Id
                        Level = $_.LevelDisplayName
                        Message = $_.Message
                        MachineName = $_.MachineName
                        UserName = $_.UserId
                    }}
                }} | ConvertTo-Json
                """
            else:
                ps_cmd = f"""
                Get-WinEvent -LogName {log_name} -MaxEvents 1000 | ForEach-Object {{
                    [PSCustomObject]@{{
                        TimeCreated = $_.TimeCreated.ToString('yyyy-MM-ddTHH:mm:ss')
                        Id = $_.Id
                        Level = $_.LevelDisplayName
                        Message = $_.Message
                        MachineName = $_.MachineName
                        UserName = $_.UserId
                    }}
                }} | ConvertTo-Json
                """

            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.warning(f"PowerShell command failed: {result.stderr}")
                return events

            data = json.loads(result.stdout)
            if not isinstance(data, list):
                data = [data]

            for item in data:
                raw_event = {
                    "timestamp": item.get("TimeCreated"),
                    "event_id": item.get("Id"),
                    "level": item.get("Level"),
                    "message": item.get("Message", ""),
                    "machine_name": item.get("MachineName", ""),
                    "user_name": item.get("UserName"),
                }
                event = SystemEvent.from_raw_event(
                    raw_event,
                    source="windows_eventlog",
                    classifier=self.classifier,
                    privacy_config=self.privacy_config,
                )
                events.append(event)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse PowerShell output: {e}")
        except subprocess.TimeoutExpired:
            logger.warning(f"PowerShell command timed out for log: {log_name}")
        except Exception as e:
            logger.error(f"Error collecting from {log_name}: {e}")

        return events

    def get_supported_logs(self) -> List[str]:
        """Windows EventLogで利用可能なログのリストを取得"""
        try:
            ps_cmd = (
                "Get-WinEvent -ListLog * | Select-Object -ExpandProperty LogName | ConvertTo-Json"
            )
            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                logs = json.loads(result.stdout)
                if not isinstance(logs, list):
                    logs = [logs]
                return logs
        except Exception as e:
            logger.warning(f"Failed to get Windows logs: {e}")

        return ["Application", "System", "Security"]
