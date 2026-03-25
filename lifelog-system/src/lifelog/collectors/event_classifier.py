"""
イベント分類・重要度判定の実装

EventClassifier インターフェースの実装。
ルールベースとイベントID/ログレベルベースの分類を提供する。
"""

import re
from typing import Optional

from .event_collector_interface import EventClassifier


def _safe_text(value: object) -> str:
    """list等が渡されても安全に文字列化する。"""
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    if value is None:
        return ""
    return str(value)


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
        event_type = "info"
        severity = 50
        category = "other"

        # ルールベースの分類
        message = _safe_text(raw_event.get("message", "")).lower()
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
        log_level = _safe_text(raw_event.get("level", "")).lower()
        level_aliases = {
            "0": "emerg",
            "1": "alert",
            "2": "crit",
            "3": "err",
            "4": "warning",
            "5": "notice",
            "6": "info",
            "7": "debug",
        }
        log_level = level_aliases.get(log_level, log_level)
        if log_level in ["error", "err"]:
            event_type, severity = "error", 70
        elif log_level in ["warning", "warn"]:
            event_type, severity = "warning", 60
        elif log_level in ["critical", "crit"]:
            event_type, severity = "critical", 90
        elif log_level in ["info"]:
            event_type, severity = "info", 40

        # メッセージパターンによるカテゴリ分類
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

        severity = max(0, min(100, severity))
        return event_type, severity, category
