"""既存の report / diary リンクを同期するメンテナンスジョブ."""

from __future__ import annotations

import argparse
import logging
import os
import re
from pathlib import Path

from src.info_collector.jobs.obsidian_links import (
    build_article_navigation_section,
    build_navigation_section,
    build_related_articles_section,
    ensure_diary_report_link,
    resolve_vault_root,
    update_raw_reports_moc,
)

logger = logging.getLogger(__name__)

REPORT_RE = re.compile(r"^report_(\d{4}-\d{2}-\d{2})\.md$")
ARTICLE_RE = re.compile(r"^article_(\d{4}-\d{2}-\d{2})_.*\.md$")
DEFAULT_YELLOWMABLE_DIR = Path(os.getenv("YELLOWMABLE_DIR", "/mnt/c/YellowMable"))
DEFAULT_REPORT_DIR = DEFAULT_YELLOWMABLE_DIR / "00_Raw"


def sync_links(output_dir: Path = DEFAULT_REPORT_DIR) -> tuple[int, int, int]:
    """既存 report と diary のリンクを同期する."""
    output_dir.mkdir(parents=True, exist_ok=True)
    vault_root = resolve_vault_root(output_dir)

    report_updated = 0
    diary_updated = 0
    article_updated = 0

    for report_path in sorted(output_dir.glob("report_*.md")):
        m = REPORT_RE.match(report_path.name)
        if not m:
            continue
        report_date = m.group(1)

        content = report_path.read_text(encoding="utf-8")
        changed = False

        if "## ナビゲーション" not in content:
            content += build_navigation_section(output_dir, report_date)
            changed = True
        if "## 関連記事" not in content:
            related = build_related_articles_section(output_dir, report_date)
            if related:
                content += related
                changed = True

        if changed:
            report_path.write_text(content, encoding="utf-8")
            report_updated += 1

        if ensure_diary_report_link(vault_root, report_date):
            diary_updated += 1

    update_raw_reports_moc(output_dir)

    for article_path in sorted(output_dir.glob("article_*.md")):
        m = ARTICLE_RE.match(article_path.name)
        if not m:
            continue
        article_date = m.group(1)
        content = article_path.read_text(encoding="utf-8")
        if "## ナビゲーション" in content:
            continue
        content += build_article_navigation_section(article_date)
        article_path.write_text(content, encoding="utf-8")
        article_updated += 1

    return report_updated, diary_updated, article_updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Obsidian links for report and diary notes.")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_REPORT_DIR))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    report_updated, diary_updated, article_updated = sync_links(Path(args.output_dir))
    logger.info(
        "Synced links: report_updated=%d, diary_updated=%d, article_updated=%d",
        report_updated,
        diary_updated,
        article_updated,
    )


if __name__ == "__main__":
    main()
