"""Obsidianリンクセクション生成ユーティリティ."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


REPORT_RE = re.compile(r"^report_(\d{4}-\d{2}-\d{2})\.md$")
ARTICLE_RE = re.compile(r"^article_(\d{4}-\d{2}-\d{2})_.*\.md$")


def resolve_vault_root(output_dir: Path) -> Path:
    """output_dir から Obsidian Vault のルートを推定する."""
    if output_dir.name == "00_Raw":
        return output_dir.parent
    return output_dir


def build_navigation_section(output_dir: Path, report_date: str) -> str:
    """report から diary/MOC/report一覧へ移動するためのナビゲーションを生成."""
    report_dates: list[str] = []
    for f in output_dir.glob("report_*.md"):
        m = REPORT_RE.match(f.name)
        if m:
            report_dates.append(m.group(1))
    report_dates = sorted(set(report_dates))

    prev_date = None
    next_date = None
    if report_date in report_dates:
        idx = report_dates.index(report_date)
        if idx > 0:
            prev_date = report_dates[idx - 1]
        if idx < len(report_dates) - 1:
            next_date = report_dates[idx + 1]

    lines = [
        "\n\n## ナビゲーション\n",
        f"- 日次ノート: [[{report_date}]]",
        f"- 年間Diary MOC: [[DiaryMOC_{report_date[:4]}]]",
        "- RawレポートMOC: [[RawReports_MOC]]",
    ]
    if prev_date:
        lines.append(f"- 前日レポート: [[report_{prev_date}]]")
    if next_date:
        lines.append(f"- 翌日レポート: [[report_{next_date}]]")
    return "\n".join(lines) + "\n"


def build_related_articles_section(output_dir: Path, report_date: str) -> str:
    """report_date に紐づく article リンクセクションを生成."""
    pattern = f"article_{report_date}_*.md"
    article_files = sorted(output_dir.glob(pattern))

    if not article_files:
        return ""

    lines = ["\n\n## 関連記事\n"]
    for f in article_files:
        lines.append(f"- [[{f.stem}]]")
    return "\n".join(lines) + "\n"


def build_article_navigation_section(article_date: str) -> str:
    """article から report/MOC/diary へ戻るナビゲーションを生成."""
    lines = [
        "\n\n## ナビゲーション\n",
        f"- 日次レポート: [[report_{article_date}]]",
        f"- 日次ノート: [[{article_date}]]",
        "- RawレポートMOC: [[RawReports_MOC]]",
    ]
    return "\n".join(lines) + "\n"


def build_obsidian_links_section(output_dir: Path, report_date: str) -> str:
    """report 用のナビゲーション + 関連記事セクションを返す."""
    return build_navigation_section(output_dir, report_date) + build_related_articles_section(
        output_dir, report_date
    )


def ensure_diary_report_link(vault_root: Path, report_date: str) -> bool:
    """01DIARY/YYYY-MM-DD.md に [[report_YYYY-MM-DD]] を追記する."""
    diary_path = vault_root / "01DIARY" / f"{report_date}.md"
    if not diary_path.exists():
        return False

    report_link = f"[[report_{report_date}]]"
    content = diary_path.read_text(encoding="utf-8")
    if report_link in content:
        return False

    section_title = "## 関連レポート"
    if section_title in content:
        new_content = content.rstrip() + f"\n- {report_link}\n"
    else:
        new_content = content.rstrip() + f"\n\n{section_title}\n- {report_link}\n"

    diary_path.write_text(new_content, encoding="utf-8")
    return True


def update_raw_reports_moc(output_dir: Path) -> Path:
    """00_Raw 配下の report/article を集約した MOC を再生成する."""
    report_dates: list[str] = []
    article_counts: dict[str, int] = {}

    for f in output_dir.glob("report_*.md"):
        m = REPORT_RE.match(f.name)
        if m:
            report_dates.append(m.group(1))

    for f in output_dir.glob("article_*.md"):
        m = ARTICLE_RE.match(f.name)
        if m:
            d = m.group(1)
            article_counts[d] = article_counts.get(d, 0) + 1

    report_dates = sorted(set(report_dates), reverse=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# RawReports_MOC",
        "",
        f"> Last updated: {now}",
        "> Auto-generated. Do not edit manually.",
        "",
        "## Daily Reports",
        "",
    ]

    if not report_dates:
        lines.append("- レポートがまだありません")
    else:
        for d in report_dates:
            count = article_counts.get(d, 0)
            lines.append(f"- {d}: [[report_{d}]] | 記事 {count} 件")

    latest_year = report_dates[0][:4] if report_dates else datetime.now().strftime("%Y")
    lines.extend(["", "## Quick Links", ""])
    lines.append(f"- [[DiaryMOC_{latest_year}]]")
    lines.append(f"- [[{latest_year}_今日の日記]]")

    moc_path = output_dir / "RawReports_MOC.md"
    moc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return moc_path
