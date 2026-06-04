import sys
from types import SimpleNamespace

from taktik.core.social_media.instagram.workflows.management.session.session import SessionManager


def test_record_action_is_local_and_does_not_require_api(monkeypatch):
    def fail_if_called():
        raise AssertionError("record_action must not use remote API quota tracking")

    monkeypatch.setitem(
        sys.modules,
        "taktik.core.database",
        SimpleNamespace(get_db_service=fail_if_called),
    )

    manager = SessionManager({"session_settings": {}})
    manager.source_counters["target_a"] = {"interactions": 0, "likes": 0}

    manager.record_action("like_posts", success=True, source="target_a")

    assert manager.counters["total_interactions"] == 1
    assert manager.counters["successful_interactions"] == 1
    assert manager.counters["likes"] == 1
    assert manager.source_counters["target_a"]["interactions"] == 1
    assert manager.source_counters["target_a"]["likes"] == 1


def test_record_action_counts_story_watch_as_story_not_like():
    manager = SessionManager({"session_settings": {}})
    manager.source_counters["target_a"] = {"interactions": 0}

    manager.record_action("watch_stories", success=True, source="target_a")

    assert manager.counters["likes"] == 0
    assert manager.counters["stories_watched"] == 1
    assert manager.source_counters["target_a"]["stories_watched"] == 1
