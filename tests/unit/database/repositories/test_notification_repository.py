"""Unit tests for the cross-platform notifications repository (dedup + recency)."""

from taktik.core.database.repositories.notifications import NotificationRepository


def _row(conn, content_hash):
    return conn.execute(
        "SELECT * FROM notifications WHERE content_hash = ?", (content_hash,)
    ).fetchone()


def test_first_record_is_new_then_redundant(conn):
    repo = NotificationRepository(conn)
    kw = dict(platform="instagram", account_id=1, actor_username="alice",
              ntype="new_follower", body="alice a commencé à vous suivre")

    assert repo.record(**kw) is True   # first time -> new
    assert repo.record(**kw) is False  # re-scan -> already seen

    rows = conn.execute("SELECT * FROM notifications").fetchall()
    assert len(rows) == 1  # dedup: one physical row


def test_reseen_bumps_last_seen_but_keeps_first_seen(conn):
    repo = NotificationRepository(conn)
    kw = dict(platform="instagram", account_id=1, actor_username="bob",
              ntype="post_like", body="bob a aimé votre photo")
    repo.record(**kw)
    chash = NotificationRepository.content_hash("instagram", 1, "post_like", "bob",
                                                "bob a aimé votre photo")
    before = _row(conn, chash)
    # Force a later last_seen_at then re-record; first_seen_at must stay put.
    conn.execute("UPDATE notifications SET last_seen_at = '2000-01-01 00:00:00', "
                 "first_seen_at = '2000-01-01 00:00:00' WHERE content_hash = ?", (chash,))
    conn.commit()
    repo.record(**kw)
    after = _row(conn, chash)
    assert after["first_seen_at"] == "2000-01-01 00:00:00"  # preserved
    assert after["last_seen_at"] != "2000-01-01 00:00:00"   # bumped
    assert before is not None


def test_distinct_actor_type_account_and_quoted_content_are_separate_rows(conn):
    repo = NotificationRepository(conn)
    repo.record(platform="instagram", account_id=1, actor_username="alice",
                ntype="post_like", body="alice liked your photo")
    repo.record(platform="instagram", account_id=1, actor_username="carol",
                ntype="post_like", body="carol liked your photo")          # other actor
    repo.record(platform="instagram", account_id=2, actor_username="alice",
                ntype="post_like", body="alice liked your photo")          # other account
    repo.record(platform="instagram", account_id=1, actor_username="alice",
                ntype="comment_like", body="alice liked your comment: nice")   # other type
    repo.record(platform="instagram", account_id=1, actor_username="alice",
                ntype="comment_like", body="alice liked your comment: cool")   # other quoted content
    assert len(conn.execute("SELECT * FROM notifications").fetchall()) == 5


def test_same_follow_across_rescans_dedups_despite_volatile_body(conn):
    # The device bug: the SAME follower produced 10 rows because the body carried the relative age,
    # the action label, and the app-language phrasing — all of which change between scans.
    repo = NotificationRepository(conn)
    kw = dict(platform="instagram", account_id=1, actor_username="_demo_kid", ntype="new_follower")
    assert repo.record(**kw, body="_demo_kid started following you. 4h Follow back",
                       relative_time="4h") is True
    assert repo.record(**kw, body="_demo_kid a commencé à vous suivre. 5 h Suivre en retour",
                       relative_time="5 h") is False   # FR re-scan, older age -> same notification
    assert repo.record(**kw, body="_demo_kid started following you. 1w Follow back",
                       relative_time="1w") is False    # a week later -> still the same follow
    assert len(conn.execute("SELECT * FROM notifications").fetchall()) == 1


def test_comment_like_same_comment_dedups_but_different_comment_is_new(conn):
    repo = NotificationRepository(conn)
    kw = dict(platform="instagram", account_id=1, actor_username="alice", ntype="comment_like")
    assert repo.record(**kw, body="alice liked your comment: nice work 4h", relative_time="4h") is True
    assert repo.record(**kw, body="alice liked your comment: nice work 5h", relative_time="5h") is False
    assert repo.record(**kw, body="alice liked your comment: great post 5h", relative_time="5h") is True
    assert len(conn.execute("SELECT * FROM notifications").fetchall()) == 2


def test_actor_username_is_lowercased_and_persona_fields_stored(conn):
    repo = NotificationRepository(conn)
    repo.record(platform="instagram", account_id=1, actor_username="MixedCase",
                ntype="comment_mention", body="@me hello", label="MixedCase a mentionné…",
                relative_time="2 j", has_action=True, actor_profile_id=42)
    row = conn.execute("SELECT * FROM notifications").fetchone()
    assert row["actor_username"] == "mixedcase"
    assert row["actor_profile_id"] == 42
    assert row["label"] == "MixedCase a mentionné…"
    assert row["relative_time"] == "2 j"
    assert row["has_action"] == 1
    assert row["sync_id"] and len(row["sync_id"]) == 32  # hex(randomblob(16))


def test_known_hash_recognizes_rescanned_notification_despite_volatile_body(conn):
    # Core of the scan early-stop: a re-scanned notification must be recognised as already-known
    # even though its body changed (age/language), so the scan can stop scrolling into old territory.
    repo = NotificationRepository(conn)
    repo.record(platform="instagram", account_id=1, actor_username="alice", ntype="new_follower",
                body="alice started following you. 4h Follow back", relative_time="4h")
    known = {r[0] for r in conn.execute("SELECT content_hash FROM notifications WHERE account_id = 1")}
    # Same follow, later scan (older age, FR phrasing) -> recognised as known.
    rescan = NotificationRepository.content_hash(
        "instagram", 1, "new_follower", "alice", "alice a commencé à vous suivre. 1w Suivre en retour", "1w")
    assert rescan in known
    # A brand-new follower is NOT known.
    fresh = NotificationRepository.content_hash(
        "instagram", 1, "new_follower", "bob", "bob started following you. 2h Follow back", "2h")
    assert fresh not in known


def test_tiktok_section_without_actor_or_type(conn):
    repo = NotificationRepository(conn)
    assert repo.record(platform="tiktok", account_id=5, raw_category="activity",
                       body="3 personnes ont aimé vos vidéos") is True
    row = conn.execute("SELECT * FROM notifications WHERE platform = 'tiktok'").fetchone()
    assert row["actor_username"] is None
    assert row["type"] is None
    assert row["raw_category"] == "activity"


def test_latest_seen_at_is_the_last_scan_of_the_account(conn):
    """The scan measures « not read yet » against it: the most recent `last_seen_at` of the account."""
    repo = NotificationRepository(conn)
    assert repo.latest_seen_at("instagram", 1) is None  # nothing recorded: a first scan
    for actor in ("alice", "bob"):
        repo.record(platform="instagram", account_id=1, actor_username=actor, ntype="new_follower")
    repo.record(platform="instagram", account_id=2, actor_username="carol", ntype="new_follower")
    conn.execute("UPDATE notifications SET last_seen_at = '2000-01-01 00:00:00' WHERE account_id = 1")
    conn.execute("UPDATE notifications SET last_seen_at = '2000-01-03 00:00:00' WHERE actor_username = 'bob'")
    conn.execute("UPDATE notifications SET last_seen_at = '2000-01-09 00:00:00' WHERE account_id = 2")
    conn.commit()

    assert repo.latest_seen_at("instagram", 1) == "2000-01-03 00:00:00"
