"""
Lightweight Ollama client for local inference.

This keeps dependencies minimal and avoids tying the rest of the codebase to a
specific HTTP stack.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)
server_logger = logging.getLogger("uvicorn.error")


class OllamaClient:
    """Minimal client for Ollama's /api/generate endpoint."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        # 環境変数からbase_urlを取得、なければデフォルト値を使用
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip(
            "/"
        )
        # 環境変数からモデルを取得、なければデフォルト値を使用
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
        # 環境変数からタイムアウトを取得、なければデフォルト180秒
        self.timeout = timeout or int(os.getenv("OLLAMA_TIMEOUT", "180"))

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        *,
        caller: str | None = None,
        purpose: str = "generate",
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Call Ollama and return the concatenated response text.

        Args:
            prompt: user prompt
            system: system prompt
            options: model options (passed as-is)
        """
        payload: Dict[str, Any] = {"model": self.model, "prompt": prompt}
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options

        url = f"{self.base_url}/api/generate"
        logger.debug("Calling Ollama at %s", url)
        effective_caller = caller or os.getenv("TIMELINE_LLM_CALLER", "lifelog_system")
        effective_purpose = os.getenv("TIMELINE_LLM_PURPOSE", purpose)
        log_payload: Dict[str, Any] = {
            "event": "llm_call",
            "caller": effective_caller,
            "purpose": effective_purpose,
            "model": self.model,
            "base_url": self.base_url,
        }
        if context:
            log_payload.update({key: value for key, value in context.items() if value is not None})
        server_logger.info(
            "llm_call %s", json.dumps(log_payload, ensure_ascii=False, sort_keys=True)
        )

        resp = requests.post(url, json=payload, stream=True, timeout=self.timeout)
        resp.raise_for_status()

        output_parts: list[str] = []
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "response" in chunk:
                output_parts.append(chunk["response"])
            if chunk.get("done"):
                break

        return "".join(output_parts).strip()
