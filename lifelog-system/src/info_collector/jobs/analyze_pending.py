"""Analyze newly collected items with Ollama (LLM①)."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.ai_secretary.ollama_client import OllamaClient
from src.info_collector.prompts import theme_extraction
from src.info_collector.repository import InfoCollectorRepository

logger = logging.getLogger(__name__)

DEFAULT_DB = Path("data/ai_secretary.db")


def _run_ollama_json(client: OllamaClient, system: str, user: str) -> dict[str, Any] | None:
    try:
        response = client.generate(prompt=user, system=system, options={"temperature": 0.3})
        if not response:
            return None
        return json.loads(response)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ollama JSON generation failed: %s", exc)
        return None


def analyze_pending_articles(db_path: Path = DEFAULT_DB, batch_size: int = 10) -> int:
    """
    未分析の記事をバッチ処理し、article_analysisへ保存する。

    Returns:
        処理した件数
    """
    repo = InfoCollectorRepository(str(db_path))
    pending = repo.fetch_unanalyzed(limit=batch_size)
    if not pending:
        logger.info("No pending articles to analyze.")
        return 0

    ollama = OllamaClient()
    processed = 0

    for article in pending:
        prompts = theme_extraction.build_prompt(
            title=article["title"],
            content=article["content"] or "",
            published_at=article.get("fetched_at", "") or "",
        )

        parsed = _run_ollama_json(ollama, prompts["system"], prompts["user"])

        # フォールバック値
        analysis = {
            "importance_score": 0.3,
            "relevance_score": 0.3,
            "category": "その他",
            "keywords": [],
            "one_line_summary": (article["title"] or "")[:50],
            "model": "fallback",
        }

        if parsed:
            analysis.update(
                {
                    "importance_score": parsed.get("importance_score", analysis["importance_score"]),
                    "relevance_score": parsed.get("relevance_score", analysis["relevance_score"]),
                    "category": parsed.get("category", analysis["category"]),
                    "keywords": parsed.get("keywords", analysis["keywords"]) or [],
                    "one_line_summary": parsed.get("one_line_summary", analysis["one_line_summary"]),
                    "model": ollama.model if hasattr(ollama, "model") else "ollama",
                }
            )

        repo.save_analysis(
            article_id=article["id"],
            importance=float(analysis["importance_score"]),
            relevance=float(analysis["relevance_score"]),
            category=str(analysis["category"]),
            keywords=[str(k) for k in analysis.get("keywords", [])],
            summary=str(analysis["one_line_summary"]),
            model=str(analysis.get("model", "ollama")),
            analyzed_at=datetime.now(),
        )
        processed += 1
        logger.info("Analyzed article_id=%s (title=%s)", article["id"], article["title"])

    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze pending articles with Ollama.")
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB))
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    analyze_pending_articles(db_path=Path(args.db_path), batch_size=args.batch_size)


if __name__ == "__main__":
    main()
