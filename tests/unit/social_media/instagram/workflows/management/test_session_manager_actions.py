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


def test_there_is_no_session_story_counter():
    """`watch_stories` was counted here and fed by no workflow; nothing read it either: story
    views are passive and capped by nothing, and the end-of-run figures come from the ledger's
    STORY_WATCH rows. Removed rather than wired as a second count of those rows (2026-09-25)."""
    manager = SessionManager({"session_settings": {}})

    assert "stories_watched" not in manager.counters
    assert "stories_watched" not in manager.get_session_stats()
