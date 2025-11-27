"""
Lightweight Ollama client for local inference.

This keeps dependencies minimal and avoids tying the rest of the codebase to a
specific HTTP stack.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class OllamaClient:
    """Minimal client for Ollama's /api/generate endpoint."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3",
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

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
