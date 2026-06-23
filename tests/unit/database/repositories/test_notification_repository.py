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


def test_distinct_actor_or_body_or_account_are_separate_rows(conn):
    repo = NotificationRepository(conn)
    repo.record(platform="instagram", account_id=1, actor_username="alice",
                ntype="post_like", body="liked your photo")
    repo.record(platform="instagram", account_id=1, actor_username="carol",
                ntype="post_like", body="liked your photo")          # other actor
    repo.record(platform="instagram", account_id=1, actor_username="alice",
                ntype="post_like", body="liked your reel")            # other body
    repo.record(platform="instagram", account_id=2, actor_username="alice",
                ntype="post_like", body="liked your photo")           # other account
    assert len(conn.execute("SELECT * FROM notifications").fetchall()) == 4


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


def test_tiktok_section_without_actor_or_type(conn):
    repo = NotificationRepository(conn)
    assert repo.record(platform="tiktok", account_id=5, raw_category="activity",
                       body="3 personnes ont aimé vos vidéos") is True
    row = conn.execute("SELECT * FROM notifications WHERE platform = 'tiktok'").fetchone()
    assert row["actor_username"] is None
    assert row["type"] is None
    assert row["raw_category"] == "activity"
