"""
イベントコレクター ファクトリ

プラットフォームに応じたコレクターを生成する。
各実装クラスは個別モジュールに分割されている:
- event_classifier.py       : EventClassifierImpl
- windows_event_collector.py: WindowsEventLogCollectorImpl
- linux_syslog_collector.py : LinuxSyslogCollectorImpl
"""

import platform

from .event_classifier import EventClassifierImpl
from .event_collector_interface import EventCollector
from .linux_syslog_collector import LinuxSyslogCollectorImpl
from .windows_event_collector import WindowsEventLogCollectorImpl


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
            facility_filter=config.get("linux", {}).get(
                "facility_filter", ["kern", "user", "daemon"]
            ),
            priority_min=config.get("linux", {}).get("priority_min", "warning"),
            ignored_processes=config.get("linux", {}).get("ignored_processes", ["tee"]),
            classifier=classifier,
            privacy_config=privacy_config,
        )
    else:
        raise ValueError(f"Unsupported platform: {platform_name}")
