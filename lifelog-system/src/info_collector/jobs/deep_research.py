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
from src.info_collector.search import DDGSearchClient, filter_search_results, filter_by_relevance

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
            raw_keywords = row["keywords"] if "keywords" in row.keys() else "[]"
            keywords = json.loads(raw_keywords or "[]")
        except Exception:
            keywords = []

        # 判断理由を取得
        importance_reason = (
            row["importance_reason"] if "importance_reason" in row.keys() else ""
        ) or ""
        relevance_reason = (
            row["relevance_reason"] if "relevance_reason" in row.keys() else ""
        ) or ""

        # 1) 検索クエリ生成
        prompts = search_query_gen.build_prompt(
            theme=summary,
            keywords=[str(k) for k in keywords],
            category=row["category"] if "category" in row.keys() else "その他",
            summary=summary,
            importance_reason=importance_reason,
            relevance_reason=relevance_reason,
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
            # 基本的なフィルタリング（スニペット長、ドメイン除外）
            basic_filtered = filter_search_results(results, min_snippet_length=40)
            combined_results.extend(basic_filtered)

        if not combined_results:
            logger.warning("No search results for article_id=%s", article_id)
            continue

        # 2-1) 関連性フィルタリング（LLM使用）
        # 元の記事との関連性が高い検索結果のみを保持
        article_content = (
            row["collected_content"] if "collected_content" in row.keys() else ""
        ) or ""
        article_summary_for_filtering = article_content[:500] if article_content else summary
        
        relevant_results = filter_by_relevance(
            results=combined_results,
            article_theme=summary,
            article_summary=article_summary_for_filtering,
            keywords=[str(k) for k in keywords],
            ollama_client=ollama,
            min_relevance_score=0.5,  # 関連性スコア0.5以上を保持
        )
        
        # 関連性フィルタリング後の結果が少ない場合は、元の結果を使用（安全策）
        if len(relevant_results) < 3:
            logger.warning("Too few relevant results (%d) for article_id=%s, using all results", 
                          len(relevant_results), article_id)
            combined_results = combined_results[:10]  # 最大10件に制限
        else:
            combined_results = relevant_results[:10]  # 関連性の高い上位10件

        # 3) 検索結果統合
        # 元の分析結果を取得
        importance_score = float(
            row["importance_score"] if "importance_score" in row.keys() else 0.0
        )
        relevance_score = float(
            row["relevance_score"] if "relevance_score" in row.keys() else 0.0
        )
        # 記事内容の最初の500文字を要約として使用（既に取得済み）
        article_summary_for_synthesis = article_summary_for_filtering

        synthesis_prompts = result_synthesis.build_prompt(
            theme=summary,
            search_query=", ".join(queries),
            search_results=combined_results[:10],
            article_summary=article_summary_for_synthesis,
            importance_score=importance_score,
            relevance_score=relevance_score,
            importance_reason=importance_reason,
            relevance_reason=relevance_reason,
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
