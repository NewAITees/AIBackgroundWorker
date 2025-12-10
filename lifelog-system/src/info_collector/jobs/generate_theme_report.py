"""Generate theme-based Markdown report from deep-research results."""

from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List

from src.ai_secretary.ollama_client import OllamaClient
from src.info_collector.prompts import theme_report
from src.info_collector.repository import InfoCollectorRepository

logger = logging.getLogger(__name__)

DEFAULT_DB = Path("data/ai_secretary.db")
DEFAULT_REPORT_DIR = Path("data/reports")


def _slugify(text: str) -> str:
    """
    テキストをファイル名に使用可能なスラッグに変換.
    
    Args:
        text: 変換するテキスト
    
    Returns:
        スラッグ化されたテキスト
    """
    # 日本語や特殊文字をアンダースコアに置換
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '_', text)
    # 長すぎる場合は切り詰め
    if len(text) > 50:
        text = text[:50]
    return text.strip('_')


def generate_theme_reports(
    db_path: Path = DEFAULT_DB,
    output_dir: Path = DEFAULT_REPORT_DIR,
    min_articles: int = 1,
    skip_existing: bool = True,
) -> List[Path]:
    """
    深掘り済み記事をテーマごとにグループ化し、テーマベースレポートを生成.
    
    Args:
        db_path: データベースパス
        output_dir: レポート出力ディレクトリ
        min_articles: テーマごとの最小記事数
        skip_existing: 既存のレポートをスキップするか
    
    Returns:
        生成されたレポートファイルのパスリスト
    """
    repo = InfoCollectorRepository(str(db_path))
    theme_groups = repo.fetch_deep_research_by_theme(min_articles=min_articles)
    
    if not theme_groups:
        logger.info("No theme groups found for report generation.")
        return []
    
    report_date = datetime.now().strftime("%Y-%m-%d")
    ollama = OllamaClient()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated_paths: List[Path] = []
    
    for theme, articles in theme_groups.items():
        # ファイル名を生成（既存チェック）
        theme_slug = _slugify(theme)
        report_filename = f"article_{theme_slug}_{report_date}.md"
        report_path = output_dir / report_filename
        
        if skip_existing and report_path.exists():
            logger.info("Skipping existing report: %s", report_path)
            continue
        
        logger.info("Generating theme report for '%s' (%d articles)", theme, len(articles))
        
        # プロンプト構築
        prompts = theme_report.build_prompt(theme=theme, articles=articles, report_date=report_date)
        
        # LLMでレポート生成
        content = ""
        try:
            content = ollama.generate(
                prompt=prompts["user"],
                system=prompts["system"],
                options={"temperature": 0.5},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Theme report generation failed for '%s': %s", theme, exc)
            content = f"# レポート生成に失敗しました\n\nテーマ: {theme}\n\nデータは保存されていますが、LLM出力を取得できませんでした。\n\nエラー: {exc}"
        
        if not content:
            content = f"# レポート生成に失敗しました\n\nテーマ: {theme}\n\nデータは保存されていますが、LLM出力を取得できませんでした。"
        
        # DB保存
        repo.save_report(
            title=f"{theme} - テーマレポート",
            report_date=report_date,
            content=content,
            article_count=len(articles),
            category="theme",
            created_at=datetime.now(),
        )
        
        # ファイル保存
        report_path.write_text(content, encoding="utf-8")
        logger.info("Theme report written to %s", report_path)
        generated_paths.append(report_path)
    
    return generated_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate theme-based reports from deep-research results.")
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB))
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--min-articles", type=int, default=1, help="Minimum articles per theme")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="Skip existing reports")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false", help="Overwrite existing reports")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    paths = generate_theme_reports(
        db_path=Path(args.db_path),
        output_dir=Path(args.output_dir),
        min_articles=args.min_articles,
        skip_existing=args.skip_existing,
    )
    
    if paths:
        logger.info("Generated %d theme report(s)", len(paths))
    else:
        logger.info("No theme reports generated")


if __name__ == "__main__":
    main()
