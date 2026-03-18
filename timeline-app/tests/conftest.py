"""
テスト共通フィクスチャ

- tmp_workspace: 一時ディレクトリを workspace として設定し、テスト後にリセットする
- client: tmp_workspace を使う FastAPI TestClient
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.routers import workspace as workspace_module


@pytest.fixture()
def tmp_workspace(tmp_path):
    """一時ディレクトリを workspace として設定する。"""
    (tmp_path / "daily").mkdir()
    (tmp_path / "articles").mkdir()
    workspace_module._workspace.clear()
    workspace_module._workspace.update(
        {
            "opened": True,
            "path": str(tmp_path),
            "mode": "standalone",
            "subdirs": {"daily": True, "articles": True},
        }
    )
    yield tmp_path
    workspace_module._workspace.clear()


@pytest.fixture()
def client(tmp_workspace):
    return TestClient(app)
