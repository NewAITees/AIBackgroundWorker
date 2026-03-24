"""Ollama HTTP API 用の最小クライアント。

/api/chat + tools（function calling）を使って構造化出力を得る。
qwen3 / qwen2.5 等の tool use 対応モデルが前提。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import requests

from ..config import AIConfig

logger = logging.getLogger("uvicorn.error")

_TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "save_entry_candidates",
        "description": (
            "ユーザーの発言に対して返答テキストを返し、"
            "diary / event / todo / memo の記録候補を最大3件まで提示する。"
            "候補が不要な場合は entry_candidates を空配列にする。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reply": {"type": "string", "description": "AIの返答（日本語で簡潔に）"},
                "entry_candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["diary", "event", "todo", "memo"],
                            },
                            "title": {"type": "string"},
                            "content": {"type": "string"},
                            "timestamp": {
                                "type": "string",
                                "description": (
                                    "ISO 8601 形式の日時。未来の予定・TODO の場合は必ず設定する。"
                                    "例: 明日15時 → 翌日の 15:00:00+09:00。"
                                    "過去の出来事や時刻不明な場合は省略可。"
                                ),
                            },
                        },
                        "required": ["type", "content"],
                    },
                },
            },
            "required": ["reply", "entry_candidates"],
        },
    },
}


class OllamaClientError(RuntimeError):
    """Ollama との通信または応答解釈に失敗したときの例外。"""


@dataclass
class OllamaChatResult:
    reply: str
    entry_candidates: list[dict]


@dataclass
class OllamaSummaryResult:
    title: str
    content: str
    should_create: bool


class OllamaClient:
    def __init__(self, settings: AIConfig):
        self._settings = settings

    def generate_chat_reply(
        self,
        messages: list[dict[str, str]],
        *,
        caller: str = "chat_api",
        context: dict[str, Any] | None = None,
    ) -> OllamaChatResult:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).astimezone()
        personality_line = (
            f"\n性格・話し方: {self._settings.personality}" if self._settings.personality else ""
        )
        system_msg = {
            "role": "system",
            "content": (
                "あなたはライフログ支援AIです。日本語で短く自然に返答してください。\n"
                f"現在日時: {now.strftime('%Y-%m-%d %H:%M %Z')}（この日時を基準に「明日」「来週」等を解釈すること）\n"
                "timestamp を設定する場合は ISO 8601 形式で、タイムゾーンオフセットを必ず付けること。\n"
                "entry_candidates の content は Markdown 形式で書くこと。HTML タグは使わないこと。" + personality_line
            ),
        }
        payload_messages = [system_msg, *messages[-12:]]
        args, fallback_content = self._chat_with_tools(
            payload_messages,
            [_TOOL_DEF],
            caller=caller,
            purpose="generate_chat_reply",
            context=context,
        )
        reply = str(args.get("reply", "")).strip() or fallback_content
        candidates_raw = args.get("entry_candidates", [])

        if not reply:
            raise OllamaClientError("Ollama 応答に reply がありません")

        if not isinstance(candidates_raw, list):
            candidates_raw = []

        normalized: list[dict] = []
        for item in candidates_raw:
            if not isinstance(item, dict):
                continue
            ts = item.get("timestamp")
            normalized.append(
                {
                    "type": str(item.get("type", "")).strip(),
                    "title": str(item.get("title", "")).strip() or None,
                    "content": str(item.get("content", "")).strip(),
                    "timestamp": str(ts).strip() if ts else None,
                }
            )

        return OllamaChatResult(reply=reply, entry_candidates=normalized)

    def summarize_import_source(
        self,
        *,
        source_type: str,
        target_label: str,
        raw_summary: str,
        caller: str = "hourly_summary_worker",
        context: dict[str, Any] | None = None,
    ) -> OllamaSummaryResult:
        tool = {
            "type": "function",
            "function": {
                "name": "summarize_hour_source",
                "description": "1時間単位のログ素材を要約し、タイトルと本文を返す。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "should_create": {"type": "boolean"},
                    },
                    "required": ["title", "content", "should_create"],
                },
            },
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "あなたはライフログ要約アシスタントです。"
                    "入力された1時間分の素材を日本語で簡潔に要約してください。"
                    "source ごとの性質を保ち、activity は実際の作業内容、browser は見ていた内容、"
                    "reports は生成物の要点、system_event は重要な運用イベントだけを抽出してください。"
                    "system_event がノイズだけなら should_create=false を返してください。"
                    "本文は箇条書きではなく、2〜5文の自然な要約を基本にしてください。"
                    "content は Markdown 形式で書くこと。HTML タグは使わないこと。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"source: {source_type}\n"
                    f"target: {target_label}\n"
                    "以下の素材を要約してください。\n"
                    f"{raw_summary}"
                ),
            },
        ]
        merged_context = {"source_type": source_type, "target_label": target_label}
        if context:
            merged_context.update(context)
        args, fallback_content = self._chat_with_tools(
            messages,
            [tool],
            caller=caller,
            purpose=f"summarize_{source_type}",
            context=merged_context,
        )
        title = str(args.get("title", "")).strip()
        content = str(args.get("content", "")).strip() or fallback_content
        should_create = bool(args.get("should_create", True))

        if not content:
            raise OllamaClientError("要約結果の content が空です")
        if not title:
            title = target_label
        return OllamaSummaryResult(title=title, content=content, should_create=should_create)

    def edit_entry_content(
        self,
        *,
        current_content: str,
        instruction: str,
        caller: str = "entry_ai_edit",
        context: dict[str, Any] | None = None,
    ) -> str:
        tool = {
            "type": "function",
            "function": {
                "name": "edit_entry_content",
                "description": "指示に従って本文全体を編集し、編集後の全文を返す。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "edited_content": {
                            "type": "string",
                            "description": "編集後の Markdown 本文全文",
                        }
                    },
                    "required": ["edited_content"],
                },
            },
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "あなたは Markdown 本文を編集するアシスタントです。"
                    "ユーザー指示に従って本文全体を書き換えてください。"
                    "指示されていない情報は勝手に削除しないこと。"
                    "出力は編集後の Markdown 本文全文とし、説明文や前置きは不要です。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"指示:\n{instruction.strip()}\n\n" "現在の本文:\n" f"{current_content.rstrip()}"
                ),
            },
        ]
        args, fallback_content = self._chat_with_tools(
            messages,
            [tool],
            caller=caller,
            purpose="edit_entry_content",
            context=context,
        )
        edited_content = str(args.get("edited_content", "")).strip() or fallback_content.strip()
        if not edited_content:
            raise OllamaClientError("編集結果が空です")
        return edited_content

    def check_health(self) -> dict:
        """Ollama の到達性と利用モデル設定を返す。"""
        try:
            response = requests.get(
                f"{self._settings.ollama_base_url.rstrip('/')}/api/tags",
                timeout=min(self._settings.timeout_seconds, 5),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return {
                "reachable": False,
                "base_url": self._settings.ollama_base_url,
                "model": self._settings.ollama_model,
                "detail": str(exc),
            }

        models = response.json().get("models", [])
        available = {
            item.get("name") for item in models if isinstance(item, dict) and item.get("name")
        }
        return {
            "reachable": True,
            "base_url": self._settings.ollama_base_url,
            "model": self._settings.ollama_model,
            "model_available": self._settings.ollama_model in available,
        }

    def _chat_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict],
        *,
        caller: str = "timeline_app",
        purpose: str = "chat_with_tools",
        context: dict[str, Any] | None = None,
    ) -> tuple[dict, str]:
        self._log_llm_call(caller=caller, purpose=purpose, context=context)
        payload = {
            "model": self._settings.ollama_model,
            "stream": False,
            "messages": messages,
            "tools": tools,
        }

        try:
            response = requests.post(
                f"{self._settings.ollama_base_url.rstrip('/')}/api/chat",
                json=payload,
                timeout=self._settings.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OllamaClientError(f"Ollama への接続に失敗しました: {exc}") from exc

        message = response.json().get("message", {})
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            args = tool_calls[0].get("function", {}).get("arguments", {})
            if isinstance(args, dict):
                return args, str(message.get("content", "")).strip()
        fallback_content = str(message.get("content", "")).strip()
        parsed = self._parse_tool_markup(fallback_content)
        return parsed, fallback_content

    def _log_llm_call(
        self,
        *,
        caller: str,
        purpose: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "event": "llm_call",
            "caller": caller,
            "purpose": purpose,
            "model": self._settings.ollama_model,
            "base_url": self._settings.ollama_base_url,
        }
        if context:
            payload.update({key: value for key, value in context.items() if value is not None})
        logger.info("llm_call %s", json.dumps(payload, ensure_ascii=False, sort_keys=True))

    def _parse_tool_markup(self, content: str) -> dict:
        """
        qwen 系が tool_calls をネイティブで返さず、
        content に {"name": ..., "arguments": {...}} を埋める場合を救済する。
        """
        if not content:
            return {}

        candidates = re.findall(r"\{.*\}", content, flags=re.DOTALL)
        for candidate in reversed(candidates):
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                arguments = payload.get("arguments")
                if isinstance(arguments, dict):
                    return arguments
        return {}
