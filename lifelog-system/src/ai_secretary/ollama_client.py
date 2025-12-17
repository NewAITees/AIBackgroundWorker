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
        self.model = model or os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
        # 環境変数からタイムアウトを取得、なければデフォルト90秒
        self.timeout = timeout or int(os.getenv("OLLAMA_TIMEOUT", "90"))

    def generate(
        self, prompt: str, system: Optional[str] = None, options: Optional[Dict[str, Any]] = None
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
