"""
Search planner that proposes queries based on interests and recent data.

It optionally asks an Ollama endpoint to generate fresh queries; when unavailable,
it falls back to user-specified queries and recent titles.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Sequence

from .repository import InfoCollectorRepository
from .models import CollectedInfo
from src.ai_secretary.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class OllamaSearchPlanner:
    """Generate search queries using Ollama with safe fallbacks."""

    def __init__(
        self,
        repository: InfoCollectorRepository,
        interests_path: Path | str | None = None,
        base_queries: Sequence[str] | None = None,
        ollama_client: OllamaClient | None = None,
    ) -> None:
        self.repository = repository
        self.interests_path = Path(interests_path) if interests_path else None
        self.base_queries = list(base_queries) if base_queries else []
        self.ollama_client = ollama_client or OllamaClient()

    def plan_queries(
        self, use_ollama: bool = True, limit: int = 10, recent_days: int = 2
    ) -> List[str]:
        """Return a prioritized list of queries."""
        interests = self._load_interests()
        recent_info = self._load_recent_info(days=recent_days, limit=40)

        # If Ollama is disabled, go straight to fallback
        if not use_ollama:
            return self._fallback_queries(interests, recent_info, limit)

        prompt = self._build_prompt(interests, recent_info, limit)
        try:
            response = self.ollama_client.generate(
                prompt=prompt,
                system=(
                    "You propose concise web search queries for news/RSS monitoring. "
                    "Prefer diverse topics tied to the given interests and recent articles. "
                    "Return only a JSON list of strings. Avoid duplicates."
                ),
            )
            queries = self._parse_queries(response)
            queries = self._dedupe_keep_order(queries)
            if not queries:
                raise ValueError("Empty query list from Ollama")
            return queries[:limit]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falling back to heuristic queries: %s", exc)
            return self._fallback_queries(interests, recent_info, limit)

    def _load_interests(self) -> List[str]:
        if not self.interests_path or not self.interests_path.exists():
            return []
        lines: List[str] = []
        with open(self.interests_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    lines.append(line)
        return lines

    def _load_recent_info(self, days: int, limit: int) -> List[CollectedInfo]:
        cutoff = datetime.now() - timedelta(days=days)
        return self.repository.search_info(
            start_date=cutoff,
            end_date=None,
            limit=limit,
        )

    def _build_prompt(
        self, interests: Sequence[str], recent_info: Sequence[CollectedInfo], limit: int
    ) -> str:
        prompt_lines: List[str] = []
        if interests:
            prompt_lines.append("User interests:")
            for topic in interests:
                prompt_lines.append(f"- {topic}")
            prompt_lines.append("")

        if recent_info:
            prompt_lines.append("Recent articles seen:")
            for info in recent_info[:10]:
                prompt_lines.append(f"- {info.title}")
            prompt_lines.append("")

        prompt_lines.append(
            f"Propose up to {limit} web search queries to discover fresh information. "
            "Return a JSON array of strings, Japanese is OK. Keep queries concise."
        )
        return "\n".join(prompt_lines)

    def _parse_queries(self, text: str) -> List[str]:
        """Best-effort parse of LLM output."""
        text = text.strip()
        if not text:
            return []

        # Try JSON first
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                # Accept {"queries": [...]} pattern
                if "queries" in parsed and isinstance(parsed["queries"], list):
                    return [str(q).strip() for q in parsed["queries"] if str(q).strip()]
            if isinstance(parsed, list):
                return [str(q).strip() for q in parsed if str(q).strip()]
        except json.JSONDecodeError:
            pass

        # Fallback: line-based split, strip bullets/numbers
        queries: List[str] = []
        for line in text.splitlines():
            line = line.strip().lstrip("-•*0123456789. ").strip()
            if line:
                queries.append(line)
        return queries

    def _fallback_queries(
        self, interests: Sequence[str], recent_info: Sequence[CollectedInfo], limit: int
    ) -> List[str]:
        """Simple heuristic: interests + base queries + recent titles keywords."""
        candidates: List[str] = []
        candidates.extend(interests)
        candidates.extend(self.base_queries)

        # Add titles as quick queries (truncated)
        for info in recent_info[:10]:
            title = info.title.strip()
            if title:
                candidates.append(title[:120])

        return self._dedupe_keep_order(candidates)[:limit]

    @staticmethod
    def _dedupe_keep_order(items: Iterable[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
        return out
