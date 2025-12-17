"""
包括的デイリーレポート生成モジュール（実装準備用）

このファイルは実装準備用です。
実装時には実際のレポート生成ロジックを実装してください。

設計ドキュメント: docs/INTEGRATED_DAILY_REPORT_DESIGN.md
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Any

from src.ai_secretary.ollama_client import OllamaClient
from src.info_collector.data_aggregator import DailyReportDataAggregator
from src.info_collector.prompts import integrated_report_generation
from src.info_collector.repository import InfoCollectorRepository

logger = logging.getLogger(__name__)

DEFAULT_LIFELOG_DB = Path("data/lifelog.db")
DEFAULT_INFO_DB = Path("data/ai_secretary.db")
DEFAULT_REPORT_DIR = Path("data/reports")


def generate_integrated_daily_report(
    lifelog_db_path: Path = DEFAULT_LIFELOG_DB,
    info_db_path: Path = DEFAULT_INFO_DB,
    output_dir: Path = DEFAULT_REPORT_DIR,
    date: Optional[str] = None,
    detail_level: str = "summary",  # 'summary', 'detailed', 'full'
    llm_client_factory: Optional[Callable[[], Any]] = None,
) -> Path | None:
    """
    包括的なデイリーレポートを生成

    Args:
        lifelog_db_path: ライフログデータベースのパス
        info_db_path: 情報収集データベースのパス
        output_dir: レポート出力ディレクトリ
        date: レポート対象日（YYYY-MM-DD）、Noneの場合は今日
        detail_level: 詳細度（'summary', 'detailed', 'full'）

    Returns:
        生成されたレポートファイルのパス、失敗時はNone
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"Generating integrated daily report for {date} (detail_level: {detail_level})")

    # 1. データ集約
    aggregator = DailyReportDataAggregator(lifelog_db_path, info_db_path)
    data = aggregator.aggregate_daily_data(date, detail_level)

    # 2. プロンプト構築（個別のリストを渡す）
    prompts = integrated_report_generation.build_integrated_prompt(
        report_date=date,
        lifelog_data=data.lifelog_data,
        events=data.events,
        browser_history=data.browser_history,
        article_analyses=data.article_analyses,
        deep_research=data.deep_research,
        theme_reports=data.theme_reports,
        timeline=data.timeline,  # UnifiedTimelineEntryのリスト
        detail_level=detail_level,
    )

    # 3. LLMでレポート生成
    llm_client = llm_client_factory() if llm_client_factory else OllamaClient()
    content = llm_client.generate(
        prompt=prompts["user"], system=prompts["system"], options={"temperature": 0.5}
    )

    if not content:
        logger.error("Failed to generate report content")
        return None

    # 4. ファイル保存
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"integrated_report_{date}.md"
    report_path.write_text(content, encoding="utf-8")
    logger.info(f"Report written to {report_path}")

    # 5. DBにも保存
    repo = InfoCollectorRepository(str(info_db_path))
    repo.save_report(
        title=f"{date} 統合デイリーレポート",
        report_date=date,
        content=content,
        article_count=len(data.article_analyses),
        category="integrated_daily",
        created_at=datetime.now(),
    )

    return report_path


def main() -> None:
    """CLIエントリーポイント"""
    parser = argparse.ArgumentParser(
        description="Generate integrated daily report from all data sources."
    )
    parser.add_argument(
        "--lifelog-db-path",
        type=str,
        default=str(DEFAULT_LIFELOG_DB),
        help="Path to lifelog database",
    )
    parser.add_argument(
        "--info-db-path",
        type=str,
        default=str(DEFAULT_INFO_DB),
        help="Path to info collector database",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_REPORT_DIR),
        help="Output directory for reports",
    )
    parser.add_argument(
        "--date", type=str, default=None, help="Report date (YYYY-MM-DD), default is today"
    )
    parser.add_argument(
        "--detail-level",
        type=str,
        choices=["summary", "detailed", "full"],
        default="summary",
        help="Detail level of the report",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    generate_integrated_daily_report(
        lifelog_db_path=Path(args.lifelog_db_path),
        info_db_path=Path(args.info_db_path),
        output_dir=Path(args.output_dir),
        date=args.date,
        detail_level=args.detail_level,
    )


if __name__ == "__main__":
    main()
