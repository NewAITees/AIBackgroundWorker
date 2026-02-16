"""Generate theme-based Markdown report from deep-research results."""

from __future__ import annotations

import argparse
import hashlib
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
DEFAULT_REPORT_DIR = Path("/mnt/c/YellowMable/00_Raw")


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

    # レポート生成日（レポート内容には使用）
    report_date = datetime.now().strftime("%Y-%m-%d")
    ollama = OllamaClient()
    output_dir.mkdir(parents=True, exist_ok=True)

    # DBから既存のハッシュ値を取得（出力フォルダと照らし合わせるため）
    existing_hashes = set(repo.get_existing_report_hashes()) if skip_existing else set()

    generated_paths: List[Path] = []

    for theme, articles in theme_groups.items():
        # 記事IDのリストを取得してソート（同じ記事セットなら常に同じハッシュになる）
        article_ids = sorted(
            [article.get("article_id") for article in articles if article.get("article_id")]
        )
        if not article_ids:
            logger.warning("No article IDs found for theme '%s', skipping", theme)
            continue

        # 記事IDのセットをハッシュ化（同じ記事セットなら常に同じファイル名になる）
        article_ids_str = ",".join(map(str, article_ids))
        article_hash = hashlib.sha256(article_ids_str.encode()).hexdigest()[:12]  # 12文字のハッシュ

        # 記事の日付を取得（published_at を優先、なければ fetched_at を使用）
        # 複数記事がある場合は最新の日付を使用
        article_dates = []
        for article in articles:
            published_at = article.get("article_published_at")
            fetched_at = article.get("article_fetched_at")
            # published_at を優先、なければ fetched_at を使用
            article_date_str = published_at if published_at else fetched_at
            if article_date_str:
                try:
                    article_date = datetime.fromisoformat(article_date_str)
                    article_dates.append(article_date)
                except (ValueError, TypeError):
                    # 日付パースに失敗した場合はスキップ
                    pass

        # 最新の日付を使用（なければ現在の日付をフォールバック）
        if article_dates:
            news_date = max(article_dates).strftime("%Y-%m-%d")
        else:
            news_date = report_date

        # テーマ名をスラッグ化（可読性のため）
        theme_slug = _slugify(theme)

        # ファイル名を生成（テーマ名とハッシュの両方を含める）
        # article_日付_テーマ_ハッシュの形式で、可読性と一意性を両立
        report_filename = f"article_{news_date}_{theme_slug}_{article_hash}.md"
        report_path = output_dir / report_filename

        # 既存チェック: DB側のハッシュ値と出力フォルダ内のファイルを照らし合わせる
        # （テーマ名が変わっても同じ記事セットならスキップ）
        if skip_existing:
            # DBに既存のハッシュ値があるかチェック
            if article_hash in existing_hashes:
                # DBに存在する場合、出力フォルダ内のファイルを検索
                existing_files = list(output_dir.glob(f"article_*_{article_hash}.md"))
                if existing_files:
                    logger.debug(
                        "Skipping existing report for article set (hash=%s): %s",
                        article_hash,
                        existing_files[0],
                    )
                    continue
                else:
                    # DBには存在するがファイルがない場合もスキップ（既に生成済みとみなす）
                    logger.debug(
                        "Skipping existing report in DB (hash=%s), but file not found in output dir",
                        article_hash,
                    )
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
            content = (
                f"# レポート生成に失敗しました\n\nテーマ: {theme}\n\nデータは保存されていますが、LLM出力を取得できませんでした。\n\nエラー: {exc}"
            )

        if not content:
            content = f"# レポート生成に失敗しました\n\nテーマ: {theme}\n\nデータは保存されていますが、LLM出力を取得できませんでした。"

        # DB保存（ハッシュ値も保存）
        repo.save_report(
            title=f"{theme} - テーマレポート",
            report_date=report_date,
            content=content,
            article_count=len(articles),
            category="theme",
            article_ids_hash=article_hash,
            created_at=datetime.now(),
        )

        # ファイル保存
        report_path.write_text(content, encoding="utf-8")
        logger.info("Theme report written to %s", report_path)
        generated_paths.append(report_path)

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
