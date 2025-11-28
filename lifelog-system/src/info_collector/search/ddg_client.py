"""DuckDuckGo検索クライアント."""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


class DDGSearchClient:
    """DuckDuckGo検索を簡易ラップ."""

    def __init__(self, max_results: int = 10, timeout: int = 10):
        self.max_results = max_results
        self.timeout = timeout

    def search(
        self, query: str, region: str = "jp-jp", time_range: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        DuckDuckGo検索を実行.

        Args:
            query: 検索クエリ
            region: 地域設定（例: jp-jp）
            time_range: 時間範囲フィルタ ("d","w","m" など)
        """
        try:
            with DDGS() as ddgs:
                results = list(
                    ddgs.text(
                        query,
                        region=region,
                        timelimit=time_range,
                        max_results=self.max_results,
                    )
                )

            standardized = [
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                }
                for r in results
            ]
            logger.info("DDG search returned %d results for: %s", len(standardized), query)
            return standardized
        except Exception as exc:  # noqa: BLE001
            logger.error("DDG search failed for '%s': %s", query, exc)
            return []

    def batch_search(self, queries: List[str], delay: float = 1.0) -> Dict[str, List[Dict]]:
        """複数クエリを順次検索（レート制限対策）。"""
        results: Dict[str, List[Dict]] = {}
        for idx, query in enumerate(queries):
            results[query] = self.search(query)
            if idx < len(queries) - 1 and delay > 0:
                time.sleep(delay)
        return results


def filter_search_results(
    results: List[Dict[str, str]], min_snippet_length: int = 50, exclude_domains: Optional[List[str]] = None
) -> List[Dict[str, str]]:
    """検索結果のフィルタリング."""
    if exclude_domains is None:
        exclude_domains = []

    filtered: List[Dict[str, str]] = []
    for result in results:
        if len(result.get("snippet", "")) < min_snippet_length:
            continue

        url = result.get("url", "")
        if any(domain in url for domain in exclude_domains):
            continue

        filtered.append(result)

    return filtered
