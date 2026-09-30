"""The follow graph is one table for two platforms — and the queries have to know it.

`social_graph_sync` is unified: it carries a `platform` column and its unique key is
`(platform, account_id, username, direction)`. Every query in the repository nevertheless said
'instagram' in SQL, so the table was multi-platform and its only reader was not. A TikTok sync
had nowhere to write and nothing to read back.

The trap this locks down is the one that costs the most: the two profile lookups used to read
the `instagram_profiles` VIEW, which is Instagram-only by construction. Pointed at a TikTok
handle, they would have answered with an Instagram namesake's follow history — no error, no
empty result, just somebody else's data.
"""

import sqlite3

import pytest

from taktik.core.database.repositories.instagram.social_graph.social_graph_repository import (
    SocialGraphRepository,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE social_graph_sync (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            account_id INTEGER NOT NULL,
            username TEXT NOT NULL COLLATE NOCASE,
            direction TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            is_reciprocal INTEGER DEFAULT NULL,
            followed_by_bot INTEGER DEFAULT 0,
            unfollowed_at TEXT DEFAULT NULL,
            first_seen_at TEXT DEFAULT (datetime('now')),
            last_seen_at TEXT DEFAULT (datetime('now')),
            source TEXT DEFAULT 'sync',
            UNIQUE(platform, account_id, username, direction)
        );
        CREATE TABLE social_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            username TEXT NOT NULL,
            legacy_profile_id INTEGER
        );
        CREATE TABLE interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            account_id INTEGER,
            profile_id INTEGER,
            interaction_type TEXT,
            success INTEGER DEFAULT 1,
            interaction_time TEXT
        );
        """
    )
    yield conn
    conn.close()


@pytest.fixture
def repos(db):
    instagram = SocialGraphRepository(db, None)
    return instagram, instagram.for_platform("tiktok")


def test_the_default_is_still_instagram():
    """Every existing caller keeps its behaviour without passing anything."""
    assert SocialGraphRepository.platform == "instagram"


def test_binding_a_platform_does_not_clone_the_connection(repos):
    instagram, tiktok = repos
    assert tiktok.platform == "tiktok"
    assert instagram.platform == "instagram"
    assert instagram.for_platform("instagram") is instagram


def test_the_same_handle_on_both_platforms_stays_two_people(repos, db):
    """The one test that separates "it works" from "it serves the neighbour's row"."""
    instagram, tiktok = repos

    instagram.upsert_following(username="marie", display_name="Marie IG", account_id=1)
    tiktok.upsert_following(username="marie", display_name="Marie TT", account_id=1)

    rows = db.execute(
        "SELECT platform, display_name FROM social_graph_sync WHERE username = 'marie' "
        "ORDER BY platform"
    ).fetchall()
    assert [(r["platform"], r["display_name"]) for r in rows] == [
        ("instagram", "Marie IG"),
        ("tiktok", "Marie TT"),
    ]


def test_a_read_never_crosses_over(repos):
    instagram, tiktok = repos
    instagram.upsert_following(username="alice", display_name="", account_id=1)
    instagram.upsert_follower(username="bob", account_id=1)

    assert instagram.get_active_following_usernames(1) == {"alice"}
    assert tiktok.get_active_following_usernames(1) == set()
    assert instagram.get_follower_usernames(1) == {"bob"}
    assert tiktok.get_follower_usernames(1) == set()


def test_the_follow_history_lookup_is_platform_scoped(repos, db):
    """Both platforms have a profile named `carla` with DIFFERENT ids, and only the Instagram
    one was ever followed. Asking TikTok must answer no."""
    instagram, tiktok = repos
    db.execute("INSERT INTO social_profiles (platform, username, legacy_profile_id) "
               "VALUES ('instagram', 'carla', 11), ('tiktok', 'carla', 22)")
    db.execute("INSERT INTO interactions (platform, account_id, profile_id, interaction_type, "
               "success, interaction_time) VALUES ('instagram', 1, 11, 'FOLLOW', 1, datetime('now'))")

    assert instagram.has_bot_follow_record("carla", 1) is True
    assert tiktok.has_bot_follow_record("carla", 1) is False


def test_a_handle_absent_from_the_platform_is_not_an_error(repos):
    _, tiktok = repos
    assert tiktok.has_bot_follow_record("nobody", 1) is False
    assert tiktok.get_days_since_follow("nobody", 1) is None
