"""Generate theme-based Markdown report from deep-research results."""

from __future__ import annotations

import argparse
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List

from src.ai_secretary.ollama_client import OllamaClient
from src.info_collector.prompts import theme_report
from src.info_collector.repository import InfoCollectorRepository

logger = logging.getLogger(__name__)

DEFAULT_DB = Path("data/ai_secretary.db")
DEFAULT_YELLOWMABLE_DIR = Path(os.getenv("YELLOWMABLE_DIR", "/mnt/c/YellowMable"))
DEFAULT_REPORT_DIR = DEFAULT_YELLOWMABLE_DIR / "00_Raw"
MIN_THEME_REPORT_CHARS = 700


def _build_theme_fallback(theme: str, articles: list[dict], report_date: str) -> str:
    lines = [
        f"# {theme} テーマレポート（フォールバック）",
        "",
        "LLM応答が不安定だったため、収集データから構造化したレポートを出力しています。",
        "",
        f"- 生成日: {report_date}",
        f"- 対象記事数: {len(articles)}",
        "",
        "## 対象記事",
    ]
    for idx, article in enumerate(articles[:12], 1):
        title = article.get("article_title", "N/A")
        url = article.get("article_url", "N/A")
        importance = article.get("importance_score", 0)
        relevance = article.get("relevance_score", 0)
        lines.append(f"{idx}. {title}")
        lines.append(f"   - URL: {url}")
        lines.append(f"   - 重要度/関連度: {importance:.2f}/{relevance:.2f}")
    lines.append("")
    lines.append("## 深掘り要約")
    for article in articles[:8]:
        summary = (article.get("synthesized_content") or "").strip()
        if len(summary) > 220:
            summary = summary[:220] + "..."
        lines.append(f"### {article.get('article_title', 'N/A')}")
        lines.append(summary or "要約なし")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _generate_theme_text(ollama: OllamaClient, prompts: dict[str, str], theme: str) -> str:
    content = ""
    for attempt in range(1, 3):
        try:
            content = ollama.generate(
                prompt=prompts["user"],
                system=prompts["system"],
                options={"temperature": 0.5},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Theme report generation failed for '%s' (attempt %d/2): %s", theme, attempt, exc
            )
            continue
        if content and len(content.strip()) >= MIN_THEME_REPORT_CHARS:
            return content
        logger.warning(
            "Theme report output too short for '%s' on attempt %d/2 (chars=%d)",
            theme,
            attempt,
            len(content or ""),
        )
    return content


def _slugify(text: str) -> str:
    """
    テキストをファイル名に使用可能なスラッグに変換.

    Unicode文字（日本語など）を含むテキストを安全なファイル名に変換します。
    非ASCII文字は保持されますが、ファイルシステムで問題となる特殊文字は
    アンダースコアに置換されます。

    Args:
        text: 変換するテキスト

    Returns:
        スラッグ化されたテキスト
    """
    # re.UNICODEフラグを使用してUnicode文字（日本語など）を保持
    # ファイル名に使用できない文字のみを除去
    # \w は re.UNICODE フラグにより Unicode の単語文字（日本語の文字など）もマッチ
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    # 連続する空白やハイフンをアンダースコアに統一
    text = re.sub(r"[-\s]+", "_", text)
    # 長すぎる場合は切り詰め
    if len(text) > 50:
        text = text[:50]
    result = text.strip("_")
    # 空文字列の場合はフォールバック（すべて非ASCII文字で構成されていた場合の対策）
    if not result:
        # 元のテキストから最初の数文字を取得してエンコード
        # ファイル名として安全な形式に変換
        result = text.encode("utf-8")[:20].hex() if text else "theme"
    return result


def generate_theme_reports(
    db_path: Path = DEFAULT_DB,
    output_dir: Path = DEFAULT_REPORT_DIR,
    min_articles: int = 1,
    skip_existing: bool = True,
    article_id: int | None = None,
) -> List[Path]:
    """
    深掘り済み記事を記事単位でレポートを生成.

    Args:
        db_path: データベースパス
        output_dir: レポート出力ディレクトリ
        min_articles: 最小記事数（後方互換のため残す、現在は記事単位なので常に1）
        skip_existing: 既存のレポートをスキップするか
        article_id: 指定した場合はその1記事のみ処理する（worker の記事単位ループ用）

    Returns:
        生成されたレポートファイルのパスリスト
    """
    repo = InfoCollectorRepository(str(db_path))
    articles = repo.fetch_deep_research_per_article(article_id=article_id)

    if not articles:
        logger.info("No deep-researched articles found for report generation.")
        return []

    report_date = datetime.now().strftime("%Y-%m-%d")
    ollama = OllamaClient()
    output_dir.mkdir(parents=True, exist_ok=True)

    existing_article_ids = repo.get_existing_report_article_ids() if skip_existing else set()

    generated_paths: List[Path] = []

    for article in articles:
        src_article_id = article.get("article_id")
        if src_article_id is None:
            logger.warning("article_id が取得できない行をスキップ")
            continue

        # 既存チェック: source_article_id が DB に既にあればスキップ
        if skip_existing and src_article_id in existing_article_ids:
            logger.debug("Skipping existing report for article_id=%s", src_article_id)
            continue

        # 記事の日付を取得（published_at を優先、なければ fetched_at）
        article_date_str = article.get("article_published_at") or article.get("article_fetched_at")
        if article_date_str:
            try:
                news_date = datetime.fromisoformat(article_date_str).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                news_date = report_date
        else:
            news_date = report_date

        # 記事タイトルをスラッグ化（可読性のため）
        article_title = article.get("article_title") or article.get("theme") or "article"
        title_slug = _slugify(article_title)

        # ファイル名: article_id で一意性を保証し、意図しない上書きを防ぐ
        report_filename = f"article_{news_date}_{title_slug}_{src_article_id}.md"
        report_path = output_dir / report_filename

        theme = article.get("theme") or article_title
        logger.info("Generating report for article_id=%s ('%s')", src_article_id, article_title)

        # プロンプト構築（単一記事をリストとして渡す）
        prompts = theme_report.build_prompt(
            theme=theme, articles=[article], report_date=report_date
        )

        # LLMでレポート生成
        content = _generate_theme_text(ollama, prompts, theme)
        if not content or len(content.strip()) < MIN_THEME_REPORT_CHARS:
            content = _build_theme_fallback(theme, [article], report_date)

        from src.info_collector.jobs.obsidian_links import build_article_navigation_section

        content += build_article_navigation_section(news_date)

        # DB保存（source_article_id で一意性を管理）
        repo.save_report(
            title=f"{article_title} - レポート",
            report_date=report_date,
            content=content,
            article_count=1,
            category="theme",
            source_article_id=src_article_id,
            created_at=datetime.now(),
        )

        # ファイル保存
        report_path.write_text(content, encoding="utf-8")
        logger.info("Report written to %s", report_path)
        generated_paths.append(report_path)

        # 次のスキップ判定に反映
        existing_article_ids.add(src_article_id)

    return generated_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate theme-based reports from deep-research results."
    )
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB))
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--min-articles", type=int, default=1, help="Minimum articles per theme")
    parser.add_argument(
        "--skip-existing", action="store_true", default=True, help="Skip existing reports"
    )
    parser.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="Overwrite existing reports",
    )
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
