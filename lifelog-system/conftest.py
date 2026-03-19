"""lifelog-system を sys.path に追加し、integration テストを制御する。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))


def pytest_collection_modifyitems(config, items):
    """integration マークのテストは -m integration を明示したときだけ実行する。"""
    markexpr = config.option.markexpr if hasattr(config.option, "markexpr") else ""
    if "integration" in markexpr:
        return  # 明示指定時はそのまま実行
    skip = pytest.mark.skip(reason="統合テストは `uv run pytest -m integration` で実行してください")
    for item in items:
        if item.get_closest_marker("integration"):
            item.add_marker(skip)
