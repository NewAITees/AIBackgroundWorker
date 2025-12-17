"""Event collector related tests."""

from datetime import datetime

from src.lifelog.collectors.event_collector import EventClassifierImpl
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
        privacy_config={"hash_messages": True, "store_message_hash_only": True, "hash_user_names": True},
    )

    assert event.message == ""  # message stripped when store_message_hash_only
    assert event.message_hash != "" and event.message_hash != raw_event["message"]
    assert event.user_name != raw_event["user_name"]
