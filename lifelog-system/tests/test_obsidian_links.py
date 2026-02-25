from pathlib import Path

from src.info_collector.jobs.obsidian_links import (
    build_navigation_section,
    ensure_diary_report_link,
    update_raw_reports_moc,
)
from src.info_collector.jobs.sync_obsidian_links import sync_links


def test_build_navigation_section_with_prev_next(tmp_path: Path):
    out = tmp_path / "00_Raw"
    out.mkdir()
    (out / "report_2026-02-16.md").write_text("x", encoding="utf-8")
    (out / "report_2026-02-17.md").write_text("x", encoding="utf-8")
    (out / "report_2026-02-18.md").write_text("x", encoding="utf-8")

    section = build_navigation_section(out, "2026-02-17")
    assert "[[2026-02-17]]" in section
    assert "[[RawReports_MOC]]" in section
    assert "[[report_2026-02-16]]" in section
    assert "[[report_2026-02-18]]" in section


def test_ensure_diary_report_link(tmp_path: Path):
    vault = tmp_path
    diary_dir = vault / "01DIARY"
    diary_dir.mkdir()
    diary = diary_dir / "2026-02-17.md"
    diary.write_text("# diary", encoding="utf-8")

    changed = ensure_diary_report_link(vault, "2026-02-17")
    assert changed is True
    content = diary.read_text(encoding="utf-8")
    assert "[[report_2026-02-17]]" in content

    changed_again = ensure_diary_report_link(vault, "2026-02-17")
    assert changed_again is False


def test_update_raw_reports_moc(tmp_path: Path):
    out = tmp_path / "00_Raw"
    out.mkdir()
    (out / "report_2026-02-17.md").write_text("x", encoding="utf-8")
    (out / "article_2026-02-17_topic_hash.md").write_text("x", encoding="utf-8")
    (out / "article_2026-02-17_topic2_hash.md").write_text("x", encoding="utf-8")

    moc = update_raw_reports_moc(out)
    text = moc.read_text(encoding="utf-8")
    assert "[[report_2026-02-17]]" in text
    assert "記事 2 件" in text


def test_sync_links_updates_report_and_diary(tmp_path: Path):
    vault = tmp_path
    out = vault / "00_Raw"
    diary_dir = vault / "01DIARY"
    out.mkdir()
    diary_dir.mkdir()

    (out / "report_2026-02-17.md").write_text("# report", encoding="utf-8")
    (out / "article_2026-02-17_a_b.md").write_text("# article", encoding="utf-8")
    (diary_dir / "2026-02-17.md").write_text("# diary", encoding="utf-8")

    report_updated, diary_updated, article_updated = sync_links(out)
    assert report_updated == 1
    assert diary_updated == 1
    assert article_updated == 1

    report_text = (out / "report_2026-02-17.md").read_text(encoding="utf-8")
    assert "## ナビゲーション" in report_text
    assert "## 関連記事" in report_text
    assert (out / "RawReports_MOC.md").exists()
    article_text = (out / "article_2026-02-17_a_b.md").read_text(encoding="utf-8")
    assert "## ナビゲーション" in article_text
