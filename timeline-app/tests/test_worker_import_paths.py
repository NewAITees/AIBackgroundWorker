"""worker の lifelog import 経路補正テスト。"""

from __future__ import annotations

import sys
from pathlib import Path

import src as timeline_src

from src.config import config
from src.workers.activity_worker import _load_lifelog_classes
from src.workers.browser_worker import _load_browser_classes


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _reset_modules(prefixes: tuple[str, ...]) -> None:
    for name in list(sys.modules):
        if name.startswith(prefixes):
            sys.modules.pop(name, None)


def test_load_lifelog_classes_adds_required_import_paths(monkeypatch):
    lifelog_root = _repo_root() / "lifelog-system"
    lifelog_src = str(lifelog_root / "src")

    monkeypatch.setattr(config.lifelog, "root_dir", str(lifelog_root))
    monkeypatch.setattr(
        sys,
        "path",
        [path for path in sys.path if path not in {str(lifelog_root), lifelog_src}],
    )
    monkeypatch.setattr(
        timeline_src,
        "__path__",
        [path for path in timeline_src.__path__ if path != lifelog_src],
    )
    _reset_modules(("lifelog.",))
    sys.modules.pop("lifelog", None)

    ActivityCollector, DatabaseManager, Config, PrivacyConfig = _load_lifelog_classes()

    assert ActivityCollector.__name__ == "ActivityCollector"
    assert DatabaseManager.__name__ == "DatabaseManager"
    assert Config.__name__ == "Config"
    assert PrivacyConfig.__name__ == "PrivacyConfig"
    assert str(lifelog_root) in sys.path
    assert lifelog_src in sys.path
    assert lifelog_src in timeline_src.__path__


def test_load_browser_classes_adds_required_import_paths(monkeypatch):
    lifelog_root = _repo_root() / "lifelog-system"
    lifelog_src = str(lifelog_root / "src")

    monkeypatch.setattr(config.lifelog, "root_dir", str(lifelog_root))
    monkeypatch.setattr(
        sys,
        "path",
        [path for path in sys.path if path not in {str(lifelog_root), lifelog_src}],
    )
    monkeypatch.setattr(
        timeline_src,
        "__path__",
        [path for path in timeline_src.__path__ if path != lifelog_src],
    )
    _reset_modules(("browser_history.",))
    sys.modules.pop("browser_history", None)

    BraveHistoryImporter, BrowserHistoryRepository = _load_browser_classes()

    assert BraveHistoryImporter.__name__ == "BraveHistoryImporter"
    assert BrowserHistoryRepository.__name__ == "BrowserHistoryRepository"
    assert str(lifelog_root) in sys.path
    assert lifelog_src in sys.path
    assert lifelog_src in timeline_src.__path__
