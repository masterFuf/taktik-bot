"""Unit tests for the notification_actions repository (audit + idempotent skip)."""

from taktik.core.database.repositories.notifications import (
    NotificationActionRepository,
    NotificationRepository,
)


def test_record_and_already_actioned(conn):
    repo = NotificationActionRepository(conn)
    chash = NotificationRepository.content_hash(
        "instagram", 1, "comment_reply", "alice", "alice replied: merci")

    assert repo.already_actioned("instagram", 1, chash, "like") is False
    repo.record(platform="instagram", account_id=1, action="like",
                actor_username="Alice", content_hash=chash, source="batch")
    assert repo.already_actioned("instagram", 1, chash, "like") is True
    # Same notification, other verb / other account: independent.
    assert repo.already_actioned("instagram", 1, chash, "reply") is False
    assert repo.already_actioned("instagram", 2, chash, "like") is False

    row = conn.execute("SELECT * FROM notification_actions").fetchone()
    assert row["actor_username"] == "alice"  # normalized lowercase
    assert row["source"] == "batch"
    assert row["success"] == 1


def test_failed_action_is_recorded_but_never_skips(conn):
    # A failure leaves an audit row yet must NOT make the retry skip: only a
    # SUCCESS makes the action idempotent.
    repo = NotificationActionRepository(conn)
    chash = NotificationRepository.content_hash(
        "instagram", 1, "new_follower", "bob", "bob a commencé à vous suivre")
    repo.record(platform="instagram", account_id=1, action="follow_back",
                actor_username="bob", content_hash=chash, success=False)
    assert repo.already_actioned("instagram", 1, chash, "follow_back") is False
    assert repo.actioned_hashes("instagram", 1, "follow_back") == set()


def test_count_today_counts_only_todays_successes(conn):
    repo = NotificationActionRepository(conn)
    repo.record(platform="instagram", account_id=1, action="follow_back", actor_username="a")
    repo.record(platform="instagram", account_id=1, action="follow_back", actor_username="b")
    repo.record(platform="instagram", account_id=1, action="follow_back", actor_username="c",
                success=False)                                        # failure: not counted
    repo.record(platform="instagram", account_id=1, action="like", actor_username="d")  # other verb
    conn.execute("UPDATE notification_actions SET created_at = '2000-01-01 00:00:00' "
                 "WHERE actor_username = 'a'")                        # yesterday: not counted
    conn.commit()
    assert repo.count_today("instagram", 1, "follow_back") == 1
    assert repo.count_today("instagram", 2, "follow_back") == 0


def test_actioned_hashes_preload_ignores_null_hashes(conn):
    # Unit actions carry no identity (hash NULL): they audit but never feed the skip set.
    repo = NotificationActionRepository(conn)
    repo.record(platform="instagram", account_id=1, action="like",
                actor_username="carol", content_hash=None)
    chash = NotificationRepository.content_hash(
        "instagram", 1, "comment_mention", "dan", "dan vous a mentionné : bravo")
    repo.record(platform="instagram", account_id=1, action="like",
                actor_username="dan", content_hash=chash)
    assert repo.actioned_hashes("instagram", 1, "like") == {chash}
