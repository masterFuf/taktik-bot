import sqlite3
from datetime import datetime, timedelta

from taktik.core.database.instagram_follow_graph import InstagramFollowGraphService
from taktik.core.database.local.schemas.instagram import (
    create_instagram_indexes,
    create_instagram_tables,
)


class _FakeLocalDb:
    def __init__(self):
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row
        cursor = self._conn.cursor()
        create_instagram_tables(cursor)
        create_instagram_indexes(cursor)
        self._conn.commit()

    def _get_connection(self):
        return self._conn


def _seed_account(fake_db, account_id=7):
    fake_db._get_connection().execute(
        "INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (?, ?, 1)",
        (account_id, f"bot_{account_id}"),
    )
    fake_db._get_connection().commit()


def test_has_bot_follow_record_and_days_since_follow(monkeypatch):
    fake_db = _FakeLocalDb()
    _seed_account(fake_db, account_id=4)
    conn = fake_db._get_connection()
    conn.execute(
        "INSERT INTO instagram_profiles (profile_id, username) VALUES (?, ?)",
        (12, "TargetUser"),
    )
    conn.execute(
        """INSERT INTO interaction_history
           (account_id, profile_id, interaction_type, interaction_time, success)
           VALUES (?, ?, 'FOLLOW', ?, 1)""",
        (4, 12, (datetime.now() - timedelta(days=5, hours=2)).isoformat()),
    )
    conn.commit()
    monkeypatch.setattr(InstagramFollowGraphService, "_local_db", staticmethod(lambda: fake_db))

    assert InstagramFollowGraphService.has_bot_follow_record("targetuser", 4) is True
    assert InstagramFollowGraphService.get_days_since_follow("targetuser", 4) == 5


def test_following_sync_upsert_and_markers(monkeypatch):
    fake_db = _FakeLocalDb()
    _seed_account(fake_db)
    monkeypatch.setattr(InstagramFollowGraphService, "_local_db", staticmethod(lambda: fake_db))

    first = InstagramFollowGraphService.sync_following_upsert(
        username="ExampleUser",
        display_name="First Name",
        account_id=7,
        followed_by_bot=True,
        source="sync",
    )
    second = InstagramFollowGraphService.sync_following_upsert(
        username="exampleuser",
        display_name="Updated Name",
        account_id=7,
        followed_by_bot=False,
        source="refresh",
    )

    InstagramFollowGraphService.mark_not_follower_back("EXAMPLEUSER", 7)
    InstagramFollowGraphService.mark_unfollowed("exampleuser", 7)

    conn = fake_db._get_connection()
    row = conn.execute(
        """SELECT display_name, followed_by_bot, is_follower_back, unfollowed_at, source
           FROM following_sync WHERE account_id = ? AND username = ? COLLATE NOCASE""",
        (7, "exampleuser"),
    ).fetchone()

    assert first == "new"
    assert second == "updated"
    assert row["display_name"] == "Updated Name"
    assert row["followed_by_bot"] == 0
    assert row["is_follower_back"] == 0
    assert row["unfollowed_at"] is not None
    assert row["source"] == "refresh"
    assert InstagramFollowGraphService.get_following_sync_usernames(7) == set()


def test_mark_follower_back_keeps_active_following_visible(monkeypatch):
    fake_db = _FakeLocalDb()
    _seed_account(fake_db, account_id=8)
    monkeypatch.setattr(InstagramFollowGraphService, "_local_db", staticmethod(lambda: fake_db))

    InstagramFollowGraphService.sync_following_upsert(
        username="MutualUser",
        display_name="Mutual",
        account_id=8,
    )
    InstagramFollowGraphService.mark_follower_back("mutualuser", 8)

    row = fake_db._get_connection().execute(
        "SELECT is_follower_back FROM following_sync WHERE account_id = ? AND username = ? COLLATE NOCASE",
        (8, "mutualuser"),
    ).fetchone()

    assert row["is_follower_back"] == 1
    assert InstagramFollowGraphService.get_following_sync_usernames(8) == {"mutualuser"}


def test_followers_sync_upsert_and_listing(monkeypatch):
    fake_db = _FakeLocalDb()
    _seed_account(fake_db, account_id=9)
    monkeypatch.setattr(InstagramFollowGraphService, "_local_db", staticmethod(lambda: fake_db))

    first = InstagramFollowGraphService.sync_follower_upsert(
        username="FanUser",
        account_id=9,
        display_name="Fan",
        is_following_back=False,
        source="full_sync",
    )
    second = InstagramFollowGraphService.sync_follower_upsert(
        username="fanuser",
        account_id=9,
        display_name="",
        is_following_back=True,
        source="mutual_detection",
    )

    row = fake_db._get_connection().execute(
        """SELECT display_name, is_following_back, source
           FROM followers_sync WHERE account_id = ? AND username = ? COLLATE NOCASE""",
        (9, "fanuser"),
    ).fetchone()

    assert first == "new"
    assert second == "updated"
    assert row["display_name"] == "Fan"
    assert row["is_following_back"] == 1
    assert row["source"] == "mutual_detection"
    assert InstagramFollowGraphService.get_followers_sync_usernames(9) == {"fanuser"}
