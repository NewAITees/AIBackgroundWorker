"""Frontend settings markup smoke tests."""

from pathlib import Path


def test_settings_panel_has_news_tab_and_stats_targets():
    html = Path("timeline-app/frontend/index.html").read_text(encoding="utf-8")

    assert 'id="settings-tab-news"' in html
    assert 'data-settings-tab-panel="news"' in html
    assert 'id="s-news-source-stats"' in html
    assert 'id="s-news-category-stats"' in html
