"""WorkerControlService の単体テスト。"""

from __future__ import annotations

from src.services.worker_control_service import WorkerControlService, _WORKER_DEFAULTS


def test_defaults_all_enabled():
    svc = WorkerControlService()
    for wid in _WORKER_DEFAULTS:
        assert svc.is_enabled(wid) is True


def test_set_enabled_disables_worker():
    svc = WorkerControlService()
    svc.set_enabled("activity", False)
    assert svc.is_enabled("activity") is False


def test_set_enabled_reenables_worker():
    svc = WorkerControlService()
    svc.set_enabled("browser", False)
    svc.set_enabled("browser", True)
    assert svc.is_enabled("browser") is True


def test_unknown_worker_defaults_true():
    svc = WorkerControlService()
    assert svc.is_enabled("nonexistent") is True


def test_set_enabled_ignores_unknown_worker():
    svc = WorkerControlService()
    svc.set_enabled("ghost", False)  # raise しないこと
    assert svc.is_enabled("ghost") is True  # デフォルトの True のまま


def test_get_all_contains_all_workers():
    svc = WorkerControlService()
    result = svc.get_all()
    assert "workers" in result
    assert set(result["workers"].keys()) == set(_WORKER_DEFAULTS.keys())


def test_get_all_reflects_changes():
    svc = WorkerControlService()
    svc.set_enabled("info", False)
    assert svc.get_all()["workers"]["info"] is False


def test_update_all_applies_partial():
    svc = WorkerControlService()
    svc.update_all({"activity": False, "browser": False})
    assert svc.is_enabled("activity") is False
    assert svc.is_enabled("browser") is False
    assert svc.is_enabled("info") is True  # 未指定は変化なし


def test_update_all_ignores_unknown():
    svc = WorkerControlService()
    svc.update_all({"ghost": False})  # raise しないこと
    result = svc.get_all()
    assert "ghost" not in result["workers"]


def test_each_worker_is_independent():
    svc = WorkerControlService()
    svc.set_enabled("activity", False)
    for wid in _WORKER_DEFAULTS:
        if wid != "activity":
            assert svc.is_enabled(wid) is True


def test_instances_are_independent():
    svc1 = WorkerControlService()
    svc2 = WorkerControlService()
    svc1.set_enabled("daily_digest", False)
    assert svc2.is_enabled("daily_digest") is True
