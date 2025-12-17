"""
Unified entry point to collect RSS/News/Search results on a schedule.

Usage (from lifelog-system/):
    uv run python -m src.info_collector.auto_runner --all --limit 15
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List

from .config import InfoCollectorConfig
from .repository import InfoCollectorRepository
from .collectors import RSSCollector, NewsCollector, SearchCollector
from .search_planner import OllamaSearchPlanner

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Info collector runner")
    parser.add_argument("--rss", action="store_true", help="Collect RSS feeds")
    parser.add_argument("--news", action="store_true", help="Collect news sites")
    parser.add_argument("--search", action="store_true", help="Collect web search results")
    parser.add_argument("--all", action="store_true", help="Collect all sources (default)")
    parser.add_argument("--limit", type=int, default=10, help="Max items per source/query")
    parser.add_argument(
        "--use-ollama",
        action="store_true",
        default=False,
        help="Ask Ollama to propose search queries",
    )
    parser.add_argument(
        "--interests-file",
        type=str,
        default="config/info_collector/interests.txt",
        help="Path to interests.txt for query planning",
    )
    parser.add_argument(
        "--base-queries-file",
        type=str,
        default="config/info_collector/search_queries.txt",
        help="Path to search_queries.txt used as fallback/base",
    )
    return parser.parse_args()


def load_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    lines: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    return lines


def collect_rss(
    config: InfoCollectorConfig, repo: InfoCollectorRepository, limit: int
) -> Dict[str, int]:
    collector = RSSCollector()
    feeds = config.load_rss_feeds()
    if not feeds:
        logger.info("No RSS feeds configured; skipping")
        return {"feeds": 0, "saved": 0}

    entries = collector.collect_multiple(feeds, max_entries_per_feed=limit)
    saved = sum(1 for entry in entries if repo.add_info(entry))
    logger.info("RSS: %d entries (%d saved) from %d feeds", len(entries), saved, len(feeds))
    return {"feeds": len(feeds), "saved": saved}


def collect_news(
    config: InfoCollectorConfig, repo: InfoCollectorRepository, limit: int
) -> Dict[str, int]:
    collector = NewsCollector()
    sites = config.load_news_sites()
    if not sites:
        logger.info("No news sites configured; skipping")
        return {"sites": 0, "saved": 0}

    saved = 0
    total = 0
    for site in sites:
        articles = collector.collect(site_url=site, max_articles=limit)
        total += len(articles)
        for article in articles:
            if repo.add_info(article):
                saved += 1
    logger.info("News: %d articles (%d saved) from %d sites", total, saved, len(sites))
    return {"sites": len(sites), "saved": saved}


def collect_search(
    repo: InfoCollectorRepository,
    planner: OllamaSearchPlanner,
    limit: int,
    use_ollama: bool,
) -> Dict[str, int]:
    collector = SearchCollector()
    queries = planner.plan_queries(limit=limit, use_ollama=use_ollama)
    if not queries:
        logger.info("No search queries produced; skipping")
        return {"queries": 0, "saved": 0}

    saved = 0
    total = 0
    for query in queries:
        results = collector.search(query=query, limit=limit)
        total += len(results)
        for res in results:
            if repo.add_info(res):
                saved += 1
    logger.info("Search: %d results (%d saved) from %d queries", total, saved, len(queries))
    return {"queries": len(queries), "saved": saved}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    args = parse_args()
    do_all = args.all or not (args.rss or args.news or args.search)

    config = InfoCollectorConfig()
    repo = InfoCollectorRepository()

    base_queries = load_lines(Path(args.base_queries_file))
    planner = OllamaSearchPlanner(
        repository=repo,
        interests_path=Path(args.interests_file),
        base_queries=base_queries,
    )

    summary: Dict[str, Dict[str, int]] = {}

    if do_all or args.rss:
        summary["rss"] = collect_rss(config, repo, args.limit)
    if do_all or args.news:
        summary["news"] = collect_news(config, repo, args.limit)
    if do_all or args.search:
        summary["search"] = collect_search(
            repo=repo, planner=planner, limit=args.limit, use_ollama=args.use_ollama
        )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
