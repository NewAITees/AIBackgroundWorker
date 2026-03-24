"""info_worker の単体テスト。"""

from __future__ import annotations

import json
import subprocess

from src.config import config
from src.workers.info_worker import InfoWorker


def test_run_info_collection_includes_use_ollama_when_enabled(monkeypatch, tmp_path):
    worker = InfoWorker()
    lifelog_root = tmp_path / "lifelog-system"
    lifelog_root.mkdir()

    monkeypatch.setattr(config.lifelog, "root_dir", str(lifelog_root))
    monkeypatch.setattr(config.lifelog, "info_limit", 12)
    monkeypatch.setattr(config.lifelog, "info_use_ollama", True)

    captured = {}

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs["cwd"]
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({"search": {"queries": 3, "saved": 9}}),
            stderr="",
        )

    monkeypatch.setattr("src.workers.info_worker.subprocess.run", _fake_run)

    result = worker._run_info_collection()
    assert result["search"]["saved"] == 9
    assert captured["cwd"] == lifelog_root
    assert "--search" in captured["cmd"]
    assert "--use-ollama" in captured["cmd"]
    assert "12" in captured["cmd"]


def test_run_info_collection_omits_use_ollama_when_disabled(monkeypatch, tmp_path):
    worker = InfoWorker()
    lifelog_root = tmp_path / "lifelog-system"
    lifelog_root.mkdir()

    monkeypatch.setattr(config.lifelog, "root_dir", str(lifelog_root))
    monkeypatch.setattr(config.lifelog, "info_limit", 7)
    monkeypatch.setattr(config.lifelog, "info_use_ollama", False)

    captured = {}

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr("src.workers.info_worker.subprocess.run", _fake_run)

    worker._run_info_collection()
    assert "--search" in captured["cmd"]
    assert "--use-ollama" not in captured["cmd"]
    assert "7" in captured["cmd"]
