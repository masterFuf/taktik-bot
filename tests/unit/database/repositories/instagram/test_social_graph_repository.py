"""Unit tests for the Instagram social graph repository."""

from datetime import datetime, timedelta

from taktik.core.database.repositories.instagram.social_graph import SocialGraphRepository


def test_follow_history_lookups_use_profile_and_interaction_tables(conn):
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (1, 'bot', 1)")
    conn.execute("INSERT INTO instagram_profiles (profile_id, username) VALUES (10, 'Creator')")
    conn.execute(
        """INSERT INTO interaction_history
           (account_id, profile_id, interaction_type, interaction_time, success)
           VALUES (?, ?, 'FOLLOW', ?, 1)""",
        (1, 10, (datetime.now() - timedelta(days=3, hours=1)).isoformat()),
    )
    conn.commit()

    assert repo.has_bot_follow_record("creator", 1) is True
    assert repo.get_days_since_follow("creator", 1) == 3


def test_following_sync_upsert_tracks_active_and_unfollowed_entries(conn):
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (2, 'bot2', 1)")
    conn.commit()

    assert repo.upsert_following("SampleUser", "Sample", 2, followed_by_bot=True) == "new"
    assert repo.get_active_following_usernames(2) == {"sampleuser"}

    assert repo.upsert_following("sampleuser", "Updated", 2, followed_by_bot=False, source="refresh") == "updated"
    repo.set_following_follower_back("sampleuser", 2, is_follower_back=True)
    repo.mark_unfollowed("sampleuser", 2)

    row = conn.execute(
        """SELECT display_name, followed_by_bot, is_follower_back, unfollowed_at, source
           FROM following_sync WHERE account_id = ? AND username = ? COLLATE NOCASE""",
        (2, "sampleuser"),
    ).fetchone()
    assert row["display_name"] == "Updated"
    assert row["followed_by_bot"] == 0
    assert row["is_follower_back"] == 1
    assert row["unfollowed_at"] is not None
    assert row["source"] == "refresh"
    assert repo.get_active_following_usernames(2) == set()


def test_followers_sync_upsert_preserves_display_name_when_refresh_is_empty(conn):
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (3, 'bot3', 1)")
    conn.commit()

    assert repo.upsert_follower("Follower", 3, display_name="Display", is_following_back=False) == "new"
    assert repo.upsert_follower("follower", 3, display_name="", is_following_back=True, source="mutual") == "updated"

    row = conn.execute(
        """SELECT display_name, is_following_back, source
           FROM followers_sync WHERE account_id = ? AND username = ? COLLATE NOCASE""",
        (3, "follower"),
    ).fetchone()
    assert row["display_name"] == "Display"
    assert row["is_following_back"] == 1
    assert row["source"] == "mutual"
    assert repo.get_follower_usernames(3) == {"follower"}
