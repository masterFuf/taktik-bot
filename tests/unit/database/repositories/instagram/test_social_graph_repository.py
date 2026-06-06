"""Unit tests for the Instagram social graph repository."""

from datetime import datetime, timedelta

from taktik.core.database.repositories.instagram.social_graph import SocialGraphRepository
from taktik.core.database.local.migration_steps.social_graph import (
    run_social_graph_sync_migrations,
)


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


def test_social_graph_sync_dual_write_and_backfill(conn):
    """Vague B pilote: les ecritures sont mirrorees dans social_graph_sync et le
    backfill des tables legacy est idempotent."""
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (4, 'bot4', 1)")
    conn.commit()

    # Dual-write: following + reciprocal + follower
    repo.upsert_following("Alice", "Alice A", 4, followed_by_bot=True)
    repo.set_following_follower_back("alice", 4, is_follower_back=True)
    repo.upsert_follower("Bob", 4, display_name="Bob B", is_following_back=False)

    following = conn.execute(
        """SELECT direction, is_reciprocal, followed_by_bot
           FROM social_graph_sync WHERE account_id = 4 AND username = 'Alice' COLLATE NOCASE""",
    ).fetchone()
    assert following["direction"] == "following"
    assert following["is_reciprocal"] == 1
    assert following["followed_by_bot"] == 1

    follower = conn.execute(
        """SELECT direction, display_name, is_reciprocal
           FROM social_graph_sync WHERE account_id = 4 AND username = 'Bob' COLLATE NOCASE""",
    ).fetchone()
    assert follower["direction"] == "follower"
    assert follower["display_name"] == "Bob B"
    assert follower["is_reciprocal"] == 0

    # Unfollow mirrors into the unified table without dropping the row
    repo.mark_unfollowed("alice", 4)
    unfollowed = conn.execute(
        "SELECT unfollowed_at FROM social_graph_sync WHERE account_id = 4 AND username = 'Alice' COLLATE NOCASE",
    ).fetchone()
    assert unfollowed["unfollowed_at"] is not None

    # Backfill of a legacy-only row is idempotent (INSERT OR IGNORE on unique key)
    conn.execute(
        "INSERT INTO following_sync (account_id, username, display_name, is_follower_back) VALUES (4, 'legacy', 'Legacy', 1)",
    )
    conn.commit()
    run_social_graph_sync_migrations(conn.cursor())
    run_social_graph_sync_migrations(conn.cursor())
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM social_graph_sync WHERE account_id = 4 AND username = 'legacy'",
    ).fetchone()
    assert count["c"] == 1
