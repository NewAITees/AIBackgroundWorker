"""Ollama HTTP API 用の最小クライアント。

/api/chat + tools（function calling）を使って構造化出力を得る。
qwen3 / qwen2.5 等の tool use 対応モデルが前提。
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from ..config import AIConfig

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


class OllamaClient:
    def __init__(self, settings: AIConfig):
        self._settings = settings

    def generate_chat_reply(self, messages: list[dict[str, str]]) -> OllamaChatResult:
        payload = {
            "model": self._settings.ollama_model,
            "stream": False,
            "messages": messages[-12:],
            "tools": [_TOOL_DEF],
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
            reply = str(args.get("reply", "")).strip()
            candidates_raw = args.get("entry_candidates", [])
        else:
            # tool_calls が空の場合は content をそのまま reply にする
            reply = str(message.get("content", "")).strip()
            candidates_raw = []

        if not reply:
            raise OllamaClientError("Ollama 応答に reply がありません")

        if not isinstance(candidates_raw, list):
            candidates_raw = []

        normalized: list[dict] = []
        for item in candidates_raw:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "type": str(item.get("type", "")).strip(),
                    "title": str(item.get("title", "")).strip() or None,
                    "content": str(item.get("content", "")).strip(),
                }
            )

        return OllamaChatResult(reply=reply, entry_candidates=normalized)

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
