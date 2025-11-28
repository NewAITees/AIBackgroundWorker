"""Deep research for important articles (LLM②+③ + DDG)."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.ai_secretary.ollama_client import OllamaClient
from src.info_collector.prompts import search_query_gen, result_synthesis
from src.info_collector.repository import InfoCollectorRepository
from src.info_collector.search import DDGSearchClient, filter_search_results

logger = logging.getLogger(__name__)

DEFAULT_DB = Path("data/ai_secretary.db")


def _run_ollama_json(client: OllamaClient, system: str, user: str, temperature: float = 0.3) -> dict[str, Any] | None:
    try:
        response = client.generate(prompt=user, system=system, options={"temperature": temperature})
        if not response:
            return None
        return json.loads(response)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ollama JSON generation failed: %s", exc)
        return None


def deep_research_articles(
    db_path: Path = DEFAULT_DB,
    batch_size: int = 5,
    min_importance: float = 0.7,
    min_relevance: float = 0.6,
) -> int:
    """重要記事を深掘りし、deep_researchに保存."""
    repo = InfoCollectorRepository(str(db_path))
    targets = repo.fetch_deep_research_targets(
        min_importance=min_importance, min_relevance=min_relevance, limit=batch_size
    )
    if not targets:
        logger.info("No articles eligible for deep research.")
        return 0

    ollama = OllamaClient()
    ddg = DDGSearchClient(max_results=10)
    processed = 0

    for row in targets:
        article_id = row["article_id"]
        summary = row["summary"] or row["collected_title"] or ""
        keywords = []
        try:
            keywords = json.loads(row.get("keywords", "[]"))
        except Exception:
            keywords = []

        # 1) 検索クエリ生成
        prompts = search_query_gen.build_prompt(
            theme=summary,
            keywords=[str(k) for k in keywords],
            category=row.get("category", "その他"),
            summary=summary,
        )
        query_payload = _run_ollama_json(ollama, prompts["system"], prompts["user"])
        queries: List[str] = []
        if query_payload and isinstance(query_payload, dict):
            queries = [q.get("query", "") for q in query_payload.get("queries", []) if q.get("query")]

        if not queries:
            logger.warning("No queries generated for article_id=%s", article_id)
            continue

        # 2) DDG検索
        search_results_map = ddg.batch_search(queries, delay=1.5)
        combined_results: List[Dict[str, str]] = []
        for results in search_results_map.values():
            combined_results.extend(filter_search_results(results, min_snippet_length=40))

        if not combined_results:
            logger.warning("No search results for article_id=%s", article_id)
            continue

        # 3) 検索結果統合
        synthesis_prompts = result_synthesis.build_prompt(
            theme=summary,
            search_query=", ".join(queries),
            search_results=combined_results[:10],
        )
        synthesis = _run_ollama_json(ollama, synthesis_prompts["system"], synthesis_prompts["user"])

        synthesized_content = ""
        sources: List[Dict[str, str]] = []
        if synthesis:
            synthesized_content = synthesis.get("detailed_summary", "")
            sources = synthesis.get("sources", [])

        repo.save_deep_research(
            article_id=article_id,
            search_query=", ".join(queries),
            search_results=combined_results,
            synthesized_content=synthesized_content,
            sources=sources,
            researched_at=datetime.now(),
        )
        processed += 1
        logger.info("Deep research saved for article_id=%s", article_id)

    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Deep research for important articles.")
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB))
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--min-importance", type=float, default=0.7)
    parser.add_argument("--min-relevance", type=float, default=0.6)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    deep_research_articles(
        db_path=Path(args.db_path),
        batch_size=args.batch_size,
        min_importance=args.min_importance,
        min_relevance=args.min_relevance,
    )


if __name__ == "__main__":
    main()
