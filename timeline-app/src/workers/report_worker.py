"""前日分のエントリをまとめて AI に日記・レポートを生成させるワーカー。

毎日 AM report_hour 時（デフォルト 6:00）に前日分を集計し、
diary entry と memo（日次レポート）entry を生成して timeline へ保存する。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from ..ai.ollama_client import OllamaClient, OllamaClientError
from ..config import config
from ..models.entry import Entry, EntryMeta, EntrySource, EntryStatus, EntryType
from ..routers.workspace import resolve_workspace_path
from ..storage.daily_reader import read_daily_entries
from ..storage.persistence import persist_entry

logger = logging.getLogger(__name__)

_REPORT_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_daily_report",
        "description": "前日のライフログをもとに日記と日次レポートを生成する。",
        "parameters": {
            "type": "object",
            "properties": {
                "diary_title": {
                    "type": "string",
                    "description": "日記のタイトル（その日を一言で表す）",
                },
                "diary_content": {
                    "type": "string",
                    "description": "前日を振り返る日記本文。一人称・自然な文体で 2〜8 文。",
                },
                "report_title": {
                    "type": "string",
                    "description": "日次レポートのタイトル",
                },
                "report_content": {
                    "type": "string",
                    "description": "活動サマリー・気づき・明日への示唆。箇条書き可。",
                },
            },
            "required": ["diary_title", "diary_content", "report_title", "report_content"],
        },
    },
}

_RELEVANT_TYPES = {
    EntryType.system_log,
    EntryType.memo,
    EntryType.news,
    EntryType.diary,
    EntryType.event,
    EntryType.chat_user,
}


@dataclass
class ReportWorkerStatus:
    last_run_at: str | None = None
    last_target_date: str | None = None
    last_saved: int = 0
    last_error: str | None = None


class ReportWorker:
    """日次レポート・日記を自動生成するワーカー。"""

    def __init__(self) -> None:
        self._status = ReportWorkerStatus()
        self._lock = asyncio.Lock()

    def get_status(self) -> dict[str, Any]:
        return asdict(self._status)

    async def sync_once(self) -> int:
        """前日分のレポートを生成する。scheduler から呼ばれる。"""
        async with self._lock:
            return await asyncio.to_thread(self._generate_blocking)

    def _generate_blocking(self) -> int:
        self._status.last_error = None
        target_date = date.today() - timedelta(days=1)
        self._status.last_target_date = target_date.isoformat()

        workspace_path = resolve_workspace_path()
        if not workspace_path:
            logger.debug("report_worker: workspace 未設定のためスキップ")
            return 0

        entries = read_daily_entries(workspace_path, config.workspace.dirs.daily, target_date)
        relevant = [e for e in entries if e.type in _RELEVANT_TYPES]

        if not relevant:
            logger.debug("report_worker: %s のエントリなし、スキップ", target_date)
            return 0

        diary_id = f"report-diary-{target_date.isoformat()}"
        if any(e.id == diary_id for e in entries):
            logger.debug("report_worker: %s の日記生成済み、スキップ", target_date)
            return 0

        context = self._build_context(relevant)
        try:
            saved = self._call_ollama(target_date, context, workspace_path)
            self._status.last_saved = saved
            self._status.last_run_at = datetime.now(UTC).isoformat()
            logger.info("report_worker: %s のレポートを %d 件保存", target_date, saved)
            return saved
        except OllamaClientError as exc:
            self._status.last_error = str(exc)
            logger.warning("report_worker: Ollama エラー: %s", exc)
            return 0
        except Exception as exc:  # noqa: BLE001
            self._status.last_error = str(exc)
            logger.exception("report_worker: 予期しないエラー")
            return 0

    def _build_context(self, entries: list[Entry]) -> str:
        lines: list[str] = []
        for e in entries[:60]:
            ts = e.timestamp.strftime("%H:%M")
            body = (e.summary or e.content)[:200]
            lines.append(f"[{ts}] ({e.type.value}) {body}")
        return "\n".join(lines)

    def _call_ollama(self, target_date: date, context: str, workspace_path: str) -> int:
        client = OllamaClient(config.ai)
        date_str = target_date.strftime("%Y年%m月%d日")
        messages = [
            {
                "role": "system",
                "content": (
                    "あなたはライフログ支援AIです。\n"
                    "提供された前日のログをもとに、自然な日記と日次レポートを日本語で生成してください。\n"
                    "日記は一人称で書き、その日の体験・気持ちを中心にしてください。\n"
                    "レポートは活動サマリーと明日への気づきを含めてください。"
                ),
            },
            {
                "role": "user",
                "content": (f"{date_str} のログです。日記とレポートを生成してください。\n\n" f"{context}"),
            },
        ]
        args, _ = client._chat_with_tools(messages, [_REPORT_TOOL])

        diary_title = str(args.get("diary_title", f"{target_date} 日記")).strip()
        diary_content = str(args.get("diary_content", "")).strip()
        report_title = str(args.get("report_title", f"{target_date} レポート")).strip()
        report_content = str(args.get("report_content", "")).strip()

        # 前日 23:00 を diary のタイムスタンプとする
        ts_diary = datetime.combine(target_date, datetime.min.time()).replace(
            hour=23, minute=0, tzinfo=UTC
        )
        ts_report = ts_diary.replace(minute=30)

        saved = 0
        if diary_content:
            persist_entry(
                workspace_path,
                Entry(
                    id=f"report-diary-{target_date.isoformat()}",
                    type=EntryType.diary,
                    title=diary_title,
                    content=diary_content,
                    timestamp=ts_diary,
                    status=EntryStatus.active,
                    source=EntrySource.ai,
                    workspace_path=workspace_path,
                    meta=EntryMeta(),
                ),
            )
            saved += 1

        if report_content:
            persist_entry(
                workspace_path,
                Entry(
                    id=f"report-daily-{target_date.isoformat()}",
                    type=EntryType.memo,
                    title=report_title,
                    content=report_content,
                    timestamp=ts_report,
                    status=EntryStatus.active,
                    source=EntrySource.ai,
                    workspace_path=workspace_path,
                    meta=EntryMeta(),
                ),
            )
            saved += 1

        return saved


report_worker = ReportWorker()
