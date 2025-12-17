"""
イベント収集コレクターのインターフェース定義（実装準備用）

このファイルは実装準備用です。
実装時には event_collector.py として実装してください。

設計ドキュメント: docs/EVENT_COLLECTION_DESIGN.md
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
import hashlib
import json


@dataclass
class SystemEvent:
    """
    システムイベントデータモデル
    
    Attributes:
        event_timestamp: イベント発生時刻
        event_type: イベントタイプ（'error', 'warning', 'info', 'critical', 'system', 'application'）
        severity: 重要度スコア（0-100）
        source: イベントソース（'windows_eventlog', 'linux_syslog', 'application', 'system'）
        category: カテゴリ（'security', 'system', 'application', 'network', etc.）
        event_id: イベントID（Windows EventLog ID や syslog facility/priority）
        message: イベントメッセージ
        message_hash: メッセージのSHA256ハッシュ（プライバシー保護用）
        raw_data_json: 元のイベントデータ（JSON形式）
        process_name: 関連プロセス名（あれば）
        user_name: ユーザー名
        machine_name: マシン名
    """
    event_timestamp: datetime
    event_type: str
    severity: int
    source: str
    category: str
    event_id: Optional[int]
    message: str
    message_hash: str
    raw_data_json: str
    process_name: Optional[str]
    user_name: Optional[str]
    machine_name: str

    @classmethod
    def from_raw_event(
        cls,
        raw_event: dict,
        source: str,
        classifier: "EventClassifier",
        privacy_config: dict = None
    ) -> "SystemEvent":
        """
        生イベントデータからSystemEventを作成
        
        Args:
            raw_event: 生イベントデータ
            source: イベントソース
            classifier: イベント分類器
            privacy_config: プライバシー設定（hash_messages, hash_user_names等）
        
        Returns:
            SystemEventインスタンス
        """
        event_type, severity, category = classifier.classify_event(raw_event)
        
        # severityを0-100の範囲にクランプ
        severity = max(0, min(100, severity))
        
        message = raw_event.get("message", "")
        user_name = raw_event.get("user_name")
        
        # プライバシー設定に基づいてハッシュ化
        privacy_config = privacy_config or {}
        hash_messages = privacy_config.get("hash_messages", True)
        hash_user_names = privacy_config.get("hash_user_names", True)
        
        if hash_messages:
            message_hash = hashlib.sha256(message.encode()).hexdigest()
            # メッセージは空文字列にする（ハッシュのみ保存）
            if privacy_config.get("store_message_hash_only", False):
                message = ""
        else:
            message_hash = hashlib.sha256(message.encode()).hexdigest()
        
        if hash_user_names and user_name:
            user_name = hashlib.sha256(user_name.encode()).hexdigest()
        
        # タイムスタンプ変換（ISO形式またはdatetimeオブジェクトをサポート）
        timestamp_str = raw_event.get("timestamp")
        if timestamp_str:
            if isinstance(timestamp_str, str):
                try:
                    event_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except ValueError:
                    # フォールバック: 現在時刻を使用
                    event_timestamp = datetime.now()
            elif isinstance(timestamp_str, datetime):
                event_timestamp = timestamp_str
            else:
                event_timestamp = datetime.now()
        else:
            event_timestamp = datetime.now()
        
        return cls(
            event_timestamp=event_timestamp,
            event_type=event_type,
            severity=severity,
            source=source,
            category=category,
            event_id=raw_event.get("event_id"),
            message=message,
            message_hash=message_hash,
            raw_data_json=json.dumps(raw_event, ensure_ascii=False, default=str),
            process_name=raw_event.get("process_name"),
            user_name=user_name,
            machine_name=raw_event.get("machine_name", "")
        )


class EventClassifier:
    """
    イベント分類・重要度判定クラス
    
    イベントID、メッセージパターン、ログレベルなどから
    イベントタイプ、重要度、カテゴリを判定する。
    """
    
    def __init__(self, classification_rules: dict = None):
        """
        Args:
            classification_rules: 分類ルール（設定ファイルから読み込む）
        """
        self.rules = classification_rules or {}
    
    def classify_event(self, raw_event: dict) -> tuple[str, int, str]:
        """
        イベントを分類・重要度判定する
        
        Args:
            raw_event: 生イベントデータ
        
        Returns:
            (event_type, severity, category) - severityは0-100の範囲
        
        実装時には以下を考慮:
        1. イベントIDベースの分類（Windows EventLog）
        2. メッセージパターンベースの分類（self.rulesを使用）
        3. ログレベルベースの分類（Linux syslog）
        """
        # デフォルト値
        event_type = "info"
        severity = 50
        category = "other"
        
        # ルールベースの分類（実装時）
        # self.rulesからパターンマッチングを実行
        # 例:
        # for pattern, rule in self.rules.items():
        #     if re.search(pattern, raw_event.get("message", ""), re.IGNORECASE):
        #         event_type = rule.get("event_type", event_type)
        #         severity = rule.get("severity", severity)
        #         category = rule.get("category", category)
        #         break
        
        # イベントIDベースの分類（Windows EventLog）
        event_id = raw_event.get("event_id")
        if event_id:
            # 実装時: イベントIDからタイプと重要度を判定
            # 例: 1000-1999: info, 2000-2999: warning, 3000+: error
            pass
        
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
        
        # severityを0-100の範囲にクランプ
        severity = max(0, min(100, severity))
        
        return event_type, severity, category


class EventCollector(ABC):
    """
    イベント収集コレクターの基底クラス
    
    各プラットフォーム（Windows/Linux）固有の実装は
    このクラスを継承して実装する。
    """
    
    def __init__(self, classifier: EventClassifier = None):
        """
        Args:
            classifier: イベント分類器
        """
        self.classifier = classifier or EventClassifier()
    
    @abstractmethod
    def collect_events(
        self, 
        since: Optional[datetime] = None,
        event_types: Optional[List[str]] = None
    ) -> List[SystemEvent]:
        """
        イベントを収集する
        
        Args:
            since: この時刻以降のイベントを収集（Noneの場合は全期間）
            event_types: 収集するイベントタイプのリスト（Noneの場合はすべて）
        
        Returns:
            収集したイベントのリスト
        """
        pass
    
    @abstractmethod
    def get_supported_logs(self) -> List[str]:
        """
        サポートしているログのリストを取得
        
        Returns:
            ログ名のリスト（例: ['Application', 'System', 'Security']）
        """
        pass


class WindowsEventLogCollector(EventCollector):
    """
    Windows EventLog APIを使用したイベント収集
    
    実装時には pywin32 または win32evtlog を使用する。
    """
    
    def __init__(
        self,
        log_names: List[str] = None,
        classifier: EventClassifier = None
    ):
        """
        Args:
            log_names: 収集するログ名のリスト
                      ['Application', 'System', 'Security'] など
            classifier: イベント分類器
        """
        super().__init__(classifier)
        self.log_names = log_names or ["Application", "System"]
    
    def collect_events(
        self, 
        since: Optional[datetime] = None,
        event_types: Optional[List[str]] = None
    ) -> List[SystemEvent]:
        """
        Windows EventLogからイベントを収集
        
        実装例:
        - win32evtlog.OpenEventLog() でログを開く
        - win32evtlog.ReadEventLog() でイベントを読み取る
        - イベントデータをSystemEventに変換
        """
        events = []
        # TODO: 実装
        return events
    
    def get_supported_logs(self) -> List[str]:
        """Windows EventLogで利用可能なログのリストを取得"""
        # TODO: 実装
        return ["Application", "System", "Security"]


class LinuxSyslogCollector(EventCollector):
    """
    Linux syslog/journaldを使用したイベント収集
    
    実装時には systemd-journal または journalctl コマンドを使用する。
    """
    
    def __init__(
        self,
        facility_filter: List[str] = None,
        priority_min: str = "warning",
        classifier: EventClassifier = None
    ):
        """
        Args:
            facility_filter: 収集するfacilityのリスト
                            ['kern', 'user', 'daemon', 'auth'] など
            priority_min: 最小優先度（'debug', 'info', 'notice', 'warning', 'err', 'crit', 'alert', 'emerg'）
            classifier: イベント分類器
        """
        super().__init__(classifier)
        self.facility_filter = facility_filter or ["kern", "user", "daemon"]
        self.priority_min = priority_min
    
    def collect_events(
        self, 
        since: Optional[datetime] = None,
        event_types: Optional[List[str]] = None
    ) -> List[SystemEvent]:
        """
        Linux syslog/journaldからイベントを収集
        
        実装例:
        - journalctl コマンドを実行してログを取得
        - または systemd-journal ライブラリを使用
        - イベントデータをSystemEventに変換
        """
        events = []
        # TODO: 実装
        return events
    
    def get_supported_logs(self) -> List[str]:
        """Linux syslogで利用可能なfacilityのリストを取得"""
        return [
            "kern", "user", "mail", "daemon", "auth", "syslog",
            "lpr", "news", "uucp", "cron", "authpriv", "ftp",
            "local0", "local1", "local2", "local3", "local4",
            "local5", "local6", "local7"
        ]


def create_collector_for_platform(
    platform: str,
    config: dict
) -> EventCollector:
    """
    プラットフォームに応じたイベントコレクターを作成
    
    Args:
        platform: プラットフォーム名（'windows' または 'linux'）
        config: 設定辞書
    
    Returns:
        EventCollectorインスタンス
    """
    classifier = EventClassifier(config.get("classification", {}).get("rules"))
    
    if platform == "windows":
        return WindowsEventLogCollector(
            log_names=config.get("windows", {}).get("log_names"),
            classifier=classifier
        )
    elif platform == "linux":
        return LinuxSyslogCollector(
            facility_filter=config.get("linux", {}).get("facility_filter"),
            priority_min=config.get("linux", {}).get("priority_min", "warning"),
            classifier=classifier
        )
    else:
        raise ValueError(f"Unsupported platform: {platform}")
