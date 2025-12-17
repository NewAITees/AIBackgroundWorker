"""DuckDuckGo検索クライアント."""

from __future__ import annotations

import json
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
    results: List[Dict[str, str]],
    min_snippet_length: int = 50,
    exclude_domains: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    """検索結果のフィルタリング（基本的なフィルタリングのみ）."""
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


def filter_by_relevance(
    results: List[Dict[str, str]],
    article_theme: str,
    article_summary: str,
    keywords: List[str],
    ollama_client,
    min_relevance_score: float = 0.5,
) -> List[Dict[str, str]]:
    """
    検索結果を元の記事との関連性でフィルタリング（LLM使用）.

    Args:
        results: 検索結果のリスト [{"title": str, "snippet": str, "url": str}, ...]
        article_theme: 元の記事のテーマ
        article_summary: 元の記事の要約
        keywords: 元の記事のキーワードリスト
        ollama_client: OllamaClientインスタンス
        min_relevance_score: 最小関連性スコア（0.0-1.0）

    Returns:
        関連性の高い検索結果のみを返す
    """
    if not results:
        return []

    # バッチ処理で関連性チェック（一度に10件まで）
    batch_size = 10
    relevant_results: List[Dict[str, str]] = []

    for i in range(0, len(results), batch_size):
        batch = results[i : i + batch_size]

        # プロンプト構築
        results_text = ""
        for idx, result in enumerate(batch, 1):
            results_text += f"\n--- 検索結果 {idx} ---\n"
            results_text += f"タイトル: {result.get('title', 'N/A')}\n"
            results_text += f"要約: {result.get('snippet', 'N/A')[:200]}\n"
            results_text += f"URL: {result.get('url', 'N/A')}\n"

        system_prompt = """あなたは情報の関連性判定の専門家です。
与えられた元の記事と検索結果を比較し、検索結果が元の記事と関連性があるかどうかを判定してください。

判定基準:
1. 検索結果が元の記事のテーマや内容と直接関連しているか
2. 検索結果が元の記事の主張を裏付ける、または補完する情報か
3. 検索結果が元の記事のキーワードやトピックと一致しているか
4. 検索結果が全く関係ない内容でないか

出力形式（JSONのみ）:
{
    "results": [
        {
            "index": 1,
            "relevant": true,
            "relevance_score": 0.8,
            "reason": "関連性の理由"
        },
        ...
    ]
}

必ずJSON形式のみを出力してください。"""

        user_prompt = f"""以下の元の記事と検索結果を比較し、関連性を判定してください。

【元の記事のテーマ】
{article_theme}

【元の記事の要約】
{article_summary}

【元の記事のキーワード】
{', '.join(keywords) if keywords else 'なし'}

【検索結果】
{results_text}

上記の出力形式に従って、各検索結果の関連性を判定してください。"""

        try:
            response = ollama_client.generate(
                prompt=user_prompt,
                system=system_prompt,
                options={"temperature": 0.2},  # 低い温度で一貫性のある判定
            )

            if response:
                # JSONパース
                try:
                    parsed = json.loads(response)
                    if isinstance(parsed, dict) and "results" in parsed:
                        for item in parsed["results"]:
                            idx = item.get("index", 0) - 1  # 1-based to 0-based
                            if 0 <= idx < len(batch):
                                if (
                                    item.get("relevant", False)
                                    and item.get("relevance_score", 0.0) >= min_relevance_score
                                ):
                                    # 関連性スコアを結果に追加
                                    result_with_score = batch[idx].copy()
                                    result_with_score["relevance_score"] = item.get(
                                        "relevance_score", 0.0
                                    )
                                    result_with_score["relevance_reason"] = item.get("reason", "")
                                    relevant_results.append(result_with_score)
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse relevance filter response as JSON, keeping all results in batch"
                    )
                    # JSONパース失敗時は全件保持（安全策）
                    relevant_results.extend(batch)
            else:
                logger.warning("Empty response from relevance filter, keeping all results in batch")
                relevant_results.extend(batch)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Relevance filtering failed: %s, keeping all results in batch", exc)
            # エラー時は全件保持（安全策）
            relevant_results.extend(batch)

    # 関連性スコアでソート（高い順）
    relevant_results.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)

    logger.info(
        "Filtered %d results to %d relevant results (min_score=%.2f)",
        len(results),
        len(relevant_results),
        min_relevance_score,
    )

    return relevant_results
