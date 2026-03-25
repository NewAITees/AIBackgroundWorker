"""Event collector related tests."""

from datetime import datetime
from subprocess import CompletedProcess

from src.lifelog.collectors.event_classifier import EventClassifierImpl
from src.lifelog.collectors.linux_syslog_collector import LinuxSyslogCollectorImpl
from src.lifelog.collectors.event_collector_interface import SystemEvent


def test_event_classifier_accepts_list_rules():
    rules = [
        {"pattern": "disk", "event_type": "warning", "severity": 60, "category": "storage"},
    ]
    classifier = EventClassifierImpl(rules)

    event_type, severity, category = classifier.classify_event({"message": "disk error"})

    assert event_type == "warning"
    assert severity == 60
    assert category == "storage"


def test_privacy_config_hashes_message_and_user():
    raw_event = {
        "timestamp": datetime.now().isoformat(),
        "message": "secret message",
        "user_name": "alice",
    }
    event = SystemEvent.from_raw_event(
        raw_event,
        source="test",
        classifier=EventClassifierImpl(),
        privacy_config={
            "hash_messages": True,
            "store_message_hash_only": True,
            "hash_user_names": True,
        },
    )

    assert event.message == ""  # message stripped when store_message_hash_only
    assert event.message_hash != "" and event.message_hash != raw_event["message"]
    assert event.user_name != raw_event["user_name"]


def test_event_classifier_maps_numeric_syslog_priority():
    classifier = EventClassifierImpl()

    event_type, severity, category = classifier.classify_event({"level": "4", "message": "warn"})

    assert event_type == "warning"
    assert severity == 60
    assert category == "other"


def test_linux_collector_uses_warning_and_higher_priorities(monkeypatch):
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, capture_output, text, timeout):
        captured["cmd"] = cmd
        return CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "src.lifelog.collectors.linux_syslog_collector.platform.system", lambda: "Linux"
    )
    monkeypatch.setattr("src.lifelog.collectors.linux_syslog_collector.subprocess.run", fake_run)

    collector = LinuxSyslogCollectorImpl(priority_min="warning")
    collector.collect_events()

    assert "--priority=0..4" in captured["cmd"]


def test_linux_collector_skips_ignored_processes(monkeypatch):
    stdout = "\n".join(
        [
            '{"__REALTIME_TIMESTAMP":"1742600000000000","PRIORITY":"4","MESSAGE":"noise","SYSLOG_FACILITY":"3","_COMM":"tee","_UID":"0","_HOSTNAME":"host"}',
            '{"__REALTIME_TIMESTAMP":"1742600001000000","PRIORITY":"3","MESSAGE":"real error","SYSLOG_FACILITY":"0","_COMM":"kernel","_UID":"0","_HOSTNAME":"host"}',
        ]
    )

    def fake_run(cmd, capture_output, text, timeout):
        return CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(
        "src.lifelog.collectors.linux_syslog_collector.platform.system", lambda: "Linux"
    )
    monkeypatch.setattr("src.lifelog.collectors.linux_syslog_collector.subprocess.run", fake_run)

    collector = LinuxSyslogCollectorImpl(priority_min="warning", ignored_processes=["tee"])
    events = collector.collect_events()

    assert len(events) == 1
    assert events[0].process_name == "kernel"
    assert events[0].event_type == "error"
