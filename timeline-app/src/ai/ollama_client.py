"""Ollama HTTP API 用の最小クライアント。"""

from __future__ import annotations

import json
from dataclasses import dataclass

import requests

from ..config import AIConfig


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
        prompt = self._build_prompt(messages)
        payload = {
            "model": self._settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        try:
            response = requests.post(
                f"{self._settings.ollama_base_url.rstrip('/')}/api/generate",
                json=payload,
                timeout=self._settings.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OllamaClientError(f"Ollama への接続に失敗しました: {exc}") from exc

        raw = response.json().get("response", "").strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaClientError("Ollama 応答の JSON 解析に失敗しました") from exc

        reply = str(parsed.get("reply", "")).strip()
        candidates = parsed.get("entry_candidates", [])
        if not isinstance(candidates, list):
            candidates = []

        normalized: list[dict] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "type": str(item.get("type", "")).strip(),
                    "title": str(item.get("title", "")).strip() or None,
                    "content": str(item.get("content", "")).strip(),
                }
            )

        if not reply:
            raise OllamaClientError("Ollama 応答に reply がありません")

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

    def _build_prompt(self, messages: list[dict[str, str]]) -> str:
        transcript = []
        for message in messages[-12:]:
            role = message.get("role", "user")
            content = message.get("content", "")
            transcript.append(f"{role}: {content}")

        transcript_text = "\n".join(transcript)
        return (
            "あなたはライフログ支援AIです。日本語で短く自然に返答してください。\n"
            "会話内容から、必要なら diary / event / todo / memo の候補を最大3件まで推定してください。\n"
            "推定は確信が低ければ0件でよいです。\n"
            "必ず JSON のみを返してください。説明文や markdown は不要です。\n"
            '形式: {"reply":"...","entry_candidates":[{"type":"todo","title":"...","content":"..."}]}\n'
            "type は diary / event / todo / memo のいずれかのみを使ってください。\n"
            "会話履歴:\n"
            f"{transcript_text}\n"
        )
