"""Generate Markdown report from recent analysis/deep-research results."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from src.ai_secretary.ollama_client import OllamaClient
from src.info_collector.prompts import report_generation
from src.info_collector.repository import InfoCollectorRepository

logger = logging.getLogger(__name__)

DEFAULT_DB = Path("data/ai_secretary.db")
DEFAULT_REPORT_DIR = Path("data/reports")


def generate_daily_report(
    db_path: Path = DEFAULT_DB, output_dir: Path = DEFAULT_REPORT_DIR, hours: int = 24
) -> Path | None:
    """直近hours時間の分析・深掘り結果から日次レポートを生成."""
    repo = InfoCollectorRepository(str(db_path))
    since = (datetime.now() - timedelta(hours=hours)).isoformat()

    analyses = repo.fetch_recent_analysis(since)
    deep = repo.fetch_recent_deep_research(since)

    if not analyses:
        logger.info("No analyzed articles to include in report.")
        return None

    report_date = datetime.now().strftime("%Y-%m-%d")
    ollama = OllamaClient()

    prompts = report_generation.build_prompt(
        report_date=report_date,
        articles=analyses,
        deep_research=deep,
    )

    content = ""
    try:
        content = ollama.generate(prompt=prompts["user"], system=prompts["system"], options={"temperature": 0.5})
    except Exception as exc:  # noqa: BLE001
        logger.error("Report generation failed: %s", exc)

    if not content:
        content = "# レポート生成に失敗しました\n\nデータは保存されていますが、LLM出力を取得できませんでした。"

    # DB保存
    repo.save_report(
        title=f"{report_date} 情報収集レポート",
        report_date=report_date,
        content=content,
        article_count=len(analyses),
        category="daily",
        created_at=datetime.now(),
    )

    # ファイル保存
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"report_{report_date}.md"
    report_path.write_text(content, encoding="utf-8")
    logger.info("Report written to %s", report_path)
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate daily report from analysis results.")
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB))
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    generate_daily_report(db_path=Path(args.db_path), output_dir=Path(args.output_dir), hours=args.hours)


if __name__ == "__main__":
    main()
