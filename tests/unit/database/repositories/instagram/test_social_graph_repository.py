"""Unit tests for the Instagram social graph repository."""

from datetime import datetime, timedelta

from taktik.core.database.repositories.instagram.social_graph import SocialGraphRepository
from taktik.core.database.local.migration_steps.social_graph import (
    run_social_graph_sync_migrations,
)


def test_follow_history_lookups_use_profile_and_interaction_tables(conn):
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 1, 'bot', 1)")
    conn.execute("INSERT INTO social_profiles (platform, legacy_profile_id, username) VALUES ('instagram', 10, 'Creator')")
    conn.execute(
        """INSERT INTO interactions
           (platform, account_id, profile_id, interaction_type, interaction_time, success)
           VALUES ('instagram', ?, ?, 'FOLLOW', ?, 1)""",
        (1, 10, (datetime.now() - timedelta(days=3, hours=1)).isoformat()),
    )
    conn.commit()

    assert repo.has_bot_follow_record("creator", 1) is True
    assert repo.get_days_since_follow("creator", 1) == 3


def test_following_sync_upsert_tracks_active_and_unfollowed_entries(conn):
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 2, 'bot2', 1)")
    conn.commit()

    assert repo.upsert_following("SampleUser", "Sample", 2, followed_by_bot=True) == "new"
    assert repo.get_active_following_usernames(2) == {"sampleuser"}

    assert repo.upsert_following("sampleuser", "Updated", 2, followed_by_bot=False, source="refresh") == "updated"
    repo.set_following_follower_back("sampleuser", 2, is_follower_back=True)
    repo.mark_unfollowed("sampleuser", 2)

    row = conn.execute(
        """SELECT display_name, followed_by_bot, is_reciprocal AS is_follower_back, unfollowed_at, source
           FROM social_graph_sync
           WHERE account_id = ? AND username = ? COLLATE NOCASE AND direction = 'following'""",
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
    conn.execute("INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 3, 'bot3', 1)")
    conn.commit()

    assert repo.upsert_follower("Follower", 3, display_name="Display", is_following_back=False) == "new"
    assert repo.upsert_follower("follower", 3, display_name="", is_following_back=True, source="mutual") == "updated"

    row = conn.execute(
        """SELECT display_name, is_reciprocal AS is_following_back, source
           FROM social_graph_sync
           WHERE account_id = ? AND username = ? COLLATE NOCASE AND direction = 'follower'""",
        (3, "follower"),
    ).fetchone()
    assert row["display_name"] == "Display"
    assert row["is_following_back"] == 1
    assert row["source"] == "mutual"
    assert repo.get_follower_usernames(3) == {"follower"}


def test_social_graph_sync_dual_write_and_backfill(conn):
    """Writes go into the unified table, and the migration moves then drops a
    legacy table idempotently."""
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 4, 'bot4', 1)")
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

    # Phase C: a legacy-only following_sync row is migrated into social_graph_sync
    # and the legacy table is then dropped, idempotently.
    conn.execute(
        """CREATE TABLE IF NOT EXISTS following_sync (
            id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, username TEXT NOT NULL,
            display_name TEXT DEFAULT '', first_seen_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT DEFAULT (datetime('now')), is_follower_back INTEGER DEFAULT NULL,
            followed_by_bot INTEGER DEFAULT 0, unfollowed_at TEXT DEFAULT NULL, source TEXT DEFAULT 'sync',
            UNIQUE(account_id, username))"""
    )
    conn.execute(
        "INSERT INTO following_sync (account_id, username, display_name, is_follower_back) VALUES (4, 'legacy', 'Legacy', 1)",
    )
    conn.commit()
    run_social_graph_sync_migrations(conn.cursor())
    run_social_graph_sync_migrations(conn.cursor())  # idempotent
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM social_graph_sync WHERE account_id = 4 AND username = 'legacy'",
    ).fetchone()
    assert count["c"] == 1
    # the legacy table is dropped by the Phase C migration
    dropped = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='following_sync'",
    ).fetchone()
    assert dropped is None


def test_active_followings_carry_the_bot_follow_date_live_from_interactions(conn):
    """U2: the unfollow candidates' source. A hand follow has no bot date; an unfollowed row is gone."""
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 7, 'bot7', 1)")
    conn.execute("INSERT INTO social_profiles (platform, legacy_profile_id, username) VALUES ('instagram', 70, 'BotFollowed')")
    followed_at = (datetime.now() - timedelta(days=9)).isoformat()
    conn.execute(
        """INSERT INTO interactions (platform, account_id, profile_id, interaction_type, interaction_time, success)
           VALUES ('instagram', 7, 70, 'FOLLOW', ?, 1)""",
        (followed_at,),
    )
    conn.commit()
    repo.upsert_following("botfollowed", "", 7)
    repo.upsert_following("handfollowed", "", 7)
    repo.upsert_following("gone", "", 7)
    repo.mark_unfollowed("gone", 7)

    rows = {row["username"].lower(): row for row in repo.list_active_followings(7)}

    assert set(rows) == {"botfollowed", "handfollowed"}
    assert rows["botfollowed"]["last_bot_follow_at"] == followed_at
    assert rows["handfollowed"]["last_bot_follow_at"] is None
    assert rows["handfollowed"]["first_seen_at"]
    assert repo.list_active_followings(0) == []


def test_a_refollowed_account_is_active_again(conn):
    """U7: an account seen in the following list, or followed again, is followed NOW."""
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 8, 'bot8', 1)")
    conn.commit()
    repo.upsert_following("again", "", 8)
    repo.mark_unfollowed("again", 8)
    assert repo.get_active_following_usernames(8) == set()
    repo.upsert_following("Again", "", 8, followed_by_bot=True, source="bot_follow")
    assert repo.get_active_following_usernames(8) == {"again"}


def _profile(conn, legacy_id, username):
    conn.execute("INSERT INTO social_profiles (platform, legacy_profile_id, username) VALUES ('instagram', ?, ?)",
                 (legacy_id, username))


def _interaction(conn, account_id, profile_id, kind, when, success=1, platform="instagram"):
    conn.execute(
        """INSERT INTO interactions (platform, account_id, profile_id, interaction_type, interaction_time, success)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (platform, account_id, profile_id, kind, when.isoformat(), success),
    )


def test_a_bot_follow_undone_by_a_bot_unfollow_is_not_the_bot_follow_of_a_hand_refollow(conn):
    """Review 2026-09-24 (B2): followed by the bot, unfollowed by the bot, followed again by hand."""
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 11, 'b11', 1)")
    _profile(conn, 110, "x_account")
    now = datetime.now()
    _interaction(conn, 11, 110, "FOLLOW", now - timedelta(days=53))
    _interaction(conn, 11, 110, "UNFOLLOW", now - timedelta(days=44))
    conn.commit()
    repo.upsert_following("x_account", "", 11)

    rows = {r["username"]: r for r in repo.list_active_followings(11)}
    assert rows["x_account"]["last_bot_follow_at"] is None


def test_a_row_reopened_by_a_sync_is_a_new_episode_the_bot_did_not_start(conn):
    """Review 2026-09-24 (B2): unfollowed outside the bot, followed again by hand, seen by a sync."""
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 12, 'b12', 1)")
    _profile(conn, 120, "y_account")
    _interaction(conn, 12, 120, "FOLLOW", datetime.now() - timedelta(days=53))
    conn.commit()
    repo.upsert_following("y_account", "", 12)
    repo.mark_unfollowed("y_account", 12)          # the departure a complete sync saw
    repo.upsert_following("y_account", "", 12)     # a later sync sees it followed again
    repo.upsert_following("y_account", "", 12)     # and the next one: the mark survives

    row = repo.list_active_followings(12)[0]
    assert row["last_bot_follow_at"] is None
    first_seen = datetime.fromisoformat(str(row["first_seen_at"]))
    assert datetime.utcnow() - first_seen < timedelta(minutes=5)


def test_a_bot_refollow_starts_an_episode_that_is_the_bot_s(conn):
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 13, 'b13', 1)")
    _profile(conn, 130, "z_account")
    _interaction(conn, 13, 130, "FOLLOW", datetime.now() - timedelta(days=60))
    _interaction(conn, 13, 130, "UNFOLLOW", datetime.now() - timedelta(days=50))
    conn.commit()
    repo.upsert_following("z_account", "", 13)
    repo.mark_unfollowed("z_account", 13)
    repo.upsert_following("z_account", "", 13)          # reopened by a sync: not the bot's
    refollow = datetime.now()
    _interaction(conn, 13, 130, "FOLLOW", refollow)     # then the bot follows it again
    conn.commit()
    repo.upsert_following("z_account", "", 13, followed_by_bot=True, source="bot_follow")

    row = repo.list_active_followings(13)[0]
    assert row["last_bot_follow_at"] == refollow.isoformat()


def test_only_this_account_s_successful_follows_on_this_platform_count(conn):
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 14, 'b14', 1)")
    conn.execute("INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 15, 'b15', 1)")
    _profile(conn, 140, "w_account")
    when = datetime.now() - timedelta(days=10)
    _interaction(conn, 15, 140, "FOLLOW", when)                       # another account
    _interaction(conn, 14, 140, "FOLLOW", when, success=0)            # a failed follow
    _interaction(conn, 14, 140, "FOLLOW", when, platform="tiktok")    # another platform
    conn.commit()
    repo.upsert_following("w_account", "", 14)

    assert repo.list_active_followings(14)[0]["last_bot_follow_at"] is None


def test_reciprocity_is_written_for_every_active_following_after_a_complete_read(conn):
    """Review 2026-09-24 (M3): nothing wrote is_reciprocal on the following rows any more."""
    repo = SocialGraphRepository(conn)
    conn.execute("INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 16, 'b16', 1)")
    conn.commit()
    for name in ("mutual", "one_way", "gone"):
        repo.upsert_following(name, "", 16)
    repo.mark_unfollowed("gone", 16)

    assert repo.set_followings_reciprocity(16, {"Mutual", "someone_else"}) == 2

    rows = {r["username"]: r["is_reciprocal"] for r in conn.execute(
        "SELECT username, is_reciprocal FROM social_graph_sync WHERE account_id = 16 AND direction = 'following'")}
    assert rows == {"mutual": 1, "one_way": 0, "gone": None}
