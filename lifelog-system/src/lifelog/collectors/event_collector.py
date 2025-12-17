"""
イベント収集コレクター実装

Windows EventLog と Linux syslog/journald からシステムイベントを収集します。

設計ドキュメント: docs/EVENT_COLLECTION_DESIGN.md
"""

import platform
import subprocess
import re
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from .event_collector_interface import (
    SystemEvent,
    EventClassifier,
    EventCollector,
    WindowsEventLogCollector,
    LinuxSyslogCollector,
    create_collector_for_platform,
)

logger = logging.getLogger(__name__)


class EventClassifierImpl(EventClassifier):
    """イベント分類・重要度判定の実装"""

    def __init__(self, rules: Optional[dict[str, dict] | list[dict]] = None) -> None:
        """
        rules が dict/リスト両方で渡されても扱えるように正規化する.
        config ではリスト形式になっているため、そのままでも動作させる。
        """
        super().__init__(rules or {})
        # 正規化: dict -> [{"pattern": key, **value}], list はそのまま
        if isinstance(self.rules, dict):
            self._normalized_rules: list[dict] = [
                {"pattern": pattern, **(value or {})} for pattern, value in self.rules.items()
            ]
        elif isinstance(self.rules, list):
            self._normalized_rules = self.rules
        else:
            self._normalized_rules = []

    def classify_event(self, raw_event: dict) -> tuple[str, int, str]:
        """
        イベントを分類・重要度判定する

        Args:
            raw_event: 生イベントデータ

        Returns:
            (event_type, severity, category) - severityは0-100の範囲
        """
        # デフォルト値
        event_type = "info"
        severity = 50
        category = "other"

        # ルールベースの分類
        message = raw_event.get("message", "").lower()
        for rule in self._normalized_rules:
            pattern = rule.get("pattern")
            if not pattern:
                continue
            if re.search(pattern, message, re.IGNORECASE):
                event_type = rule.get("event_type", event_type)
                severity = rule.get("severity", severity)
                category = rule.get("category", category)
                break

        # イベントIDベースの分類（Windows EventLog）
        event_id = raw_event.get("event_id")
        if event_id:
            # Windows EventLog IDの範囲による分類
            if 1000 <= event_id < 2000:
                event_type = "info"
                severity = 40
            elif 2000 <= event_id < 3000:
                event_type = "warning"
                severity = 60
            elif 3000 <= event_id < 4000:
                event_type = "error"
                severity = 70
            elif event_id >= 4000:
                event_type = "critical"
                severity = 90

        # ログレベルベースの分類（Linux syslog）
        log_level = raw_event.get("level", "").lower()
        if log_level in ["error", "err"]:
            event_type = "error"
            severity = 70
        elif log_level in ["warning", "warn"]:
            event_type = "warning"
            severity = 60
        elif log_level in ["critical", "crit"]:
            event_type = "critical"
            severity = 90
        elif log_level in ["info"]:
            event_type = "info"
            severity = 40

        # メッセージパターンによる分類
        if any(keyword in message for keyword in ["security", "auth", "login", "logout"]):
            category = "security"
            if severity < 70:
                severity = 70
        elif any(keyword in message for keyword in ["network", "connection", "socket"]):
            category = "network"
        elif any(keyword in message for keyword in ["disk", "storage", "file system"]):
            category = "storage"
        elif any(keyword in message for keyword in ["performance", "slow", "timeout"]):
            category = "performance"

        # severityを0-100の範囲にクランプ
        severity = max(0, min(100, severity))

        return event_type, severity, category


class WindowsEventLogCollectorImpl(WindowsEventLogCollector):
    """Windows EventLog APIを使用したイベント収集の実装"""

    def __init__(
        self,
        log_names: List[str] = None,
        classifier: EventClassifier = None,
        privacy_config: Optional[dict] = None,
    ):
        super().__init__(log_names, classifier)
        self.privacy_config = privacy_config or {}
        self._check_windows()

    def _check_windows(self) -> None:
        """Windows環境かどうかを確認"""
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
            # PowerShellを使用してEventLogを取得
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
            # PowerShellコマンドを構築
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

            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.warning(f"PowerShell command failed: {result.stderr}")
                return events

            # JSONをパース（複数オブジェクトの場合は配列として処理）
            import json

            try:
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
            ps_cmd = "Get-WinEvent -ListLog * | Select-Object -ExpandProperty LogName | ConvertTo-Json"
            result = subprocess.run(
                ["powershell", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                import json

                logs = json.loads(result.stdout)
                if not isinstance(logs, list):
                    logs = [logs]
                return logs
        except Exception as e:
            logger.warning(f"Failed to get Windows logs: {e}")

        return ["Application", "System", "Security"]


class LinuxSyslogCollectorImpl(LinuxSyslogCollector):
    """Linux syslog/journaldを使用したイベント収集の実装"""

    def __init__(
        self,
        facility_filter: List[str] = None,
        priority_min: str = "warning",
        classifier: EventClassifier = None,
        privacy_config: Optional[dict] = None,
    ):
        super().__init__(facility_filter, priority_min, classifier)
        self.privacy_config = privacy_config or {}

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
            # journalctlコマンドを使用
            cmd = ["journalctl", "--no-pager", "--output=json"]

            if since:
                cmd.append(f"--since={since.isoformat()}")

            # 優先度フィルタ
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
                cmd.append(f"--priority={min_priority}..7")

            # facilityフィルタ
            if self.facility_filter:
                for facility in self.facility_filter:
                    cmd.append(f"--facility={facility}")

            cmd.append("--lines=1000")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.warning(f"journalctl command failed: {result.stderr}")
                return events

            # JSON Lines形式でパース
            import json

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                try:
                    item = json.loads(line)
                    raw_event = {
                        "timestamp": item.get("__REALTIME_TIMESTAMP"),
                        "level": item.get("PRIORITY"),
                        "message": item.get("MESSAGE", ""),
                        "facility": item.get("SYSLOG_FACILITY"),
                        "process_name": item.get("_COMM"),
                        "user_name": item.get("_UID"),
                        "machine_name": item.get("_HOSTNAME", ""),
                    }

                    # タイムスタンプ変換（マイクロ秒からdatetime）
                    if raw_event["timestamp"]:
                        try:
                            ts_microseconds = int(raw_event["timestamp"]) / 1_000_000
                            raw_event["timestamp"] = datetime.fromtimestamp(
                                ts_microseconds
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


def create_collector_for_platform_impl(
    platform_name: str = None,
    config: dict = None,
) -> EventCollector:
    """
    プラットフォームに応じたイベントコレクターを作成

    Args:
        platform_name: プラットフォーム名（'windows' または 'linux'）、Noneの場合は自動検出
        config: 設定辞書

    Returns:
        EventCollectorインスタンス
    """
    if platform_name is None:
        platform_name = platform.system().lower()

    config = config or {}
    classification_rules = config.get("classification", {}).get("rules", {})
    privacy_config = config.get("privacy", {})

    classifier = EventClassifierImpl(classification_rules)

    if platform_name == "windows":
        return WindowsEventLogCollectorImpl(
            log_names=config.get("windows", {}).get("log_names", ["Application", "System"]),
            classifier=classifier,
            privacy_config=privacy_config,
        )
    elif platform_name in ["linux", "linux2"]:
        return LinuxSyslogCollectorImpl(
            facility_filter=config.get("linux", {}).get("facility_filter", ["kern", "user", "daemon"]),
            priority_min=config.get("linux", {}).get("priority_min", "warning"),
            classifier=classifier,
            privacy_config=privacy_config,
        )
    else:
        raise ValueError(f"Unsupported platform: {platform_name}")
