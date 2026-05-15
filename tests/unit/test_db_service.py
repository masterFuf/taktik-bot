"""Unit tests for LocalDatabaseService — accounts, profiles, interactions, sessions."""
import pytest
from taktik.core.database.local.service import LocalDatabaseService


# ─── Accounts ─────────────────────────────────────────────────────────────────

class TestAccounts:
    def test_create_account(self, db: LocalDatabaseService):
        acc_id, created = db.get_or_create_account("testuser")
        assert created is True
        assert isinstance(acc_id, int)
        assert acc_id > 0

    def test_get_existing_account(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("testuser")
        acc_id2, created2 = db.get_or_create_account("testuser")
        assert created2 is False
        assert acc_id == acc_id2

    def test_find_by_username(self, db: LocalDatabaseService):
        db.get_or_create_account("alice")
        acc = db.get_account_by_username("alice")
        assert acc is not None
        assert acc["username"] == "alice"

    def test_find_unknown_username_returns_none(self, db: LocalDatabaseService):
        assert db.get_account_by_username("nobody") is None

    def test_multiple_accounts(self, db: LocalDatabaseService):
        ids = set()
        for name in ("alice", "bob", "charlie"):
            aid, _ = db.get_or_create_account(name)
            ids.add(aid)
        assert len(ids) == 3


# ─── Profiles ─────────────────────────────────────────────────────────────────

class TestProfiles:
    def test_create_profile(self, db: LocalDatabaseService):
        pid, created = db.get_or_create_profile({"username": "instauser"})
        assert created is True
        assert pid > 0

    def test_get_existing_profile(self, db: LocalDatabaseService):
        pid1, _ = db.get_or_create_profile({"username": "instauser"})
        pid2, created = db.get_or_create_profile({"username": "instauser"})
        assert created is False
        assert pid1 == pid2

    def test_profile_with_stats(self, db: LocalDatabaseService):
        pid, _ = db.get_or_create_profile({
            "username": "richprofile",
            "followers_count": 1000,
            "following_count": 500,
            "posts_count": 42,
            "biography": "Hello world",
        })
        profile = db.get_profile_by_username("richprofile")
        assert profile["followers_count"] == 1000
        assert profile["biography"] == "Hello world"

    def test_save_profile_records_stats_history(self, db: LocalDatabaseService):
        result = db.save_profile({
            "username": "statuser",
            "followers_count": 2000,
            "following_count": 300,
            "posts_count": 10,
        })
        assert result["profile_id"] > 0
        # Verify profile_stats_history row was created
        conn = db._get_connection()
        row = conn.execute(
            "SELECT * FROM profile_stats_history WHERE profile_id = ?",
            (result["profile_id"],),
        ).fetchone()
        assert row is not None
        assert row["followers_count"] == 2000

    def test_profile_recently_scraped(self, db: LocalDatabaseService):
        db.get_or_create_profile({"username": "freshuser"})
        assert db.is_profile_recently_scraped("freshuser", days=7) is True
        assert db.is_profile_recently_scraped("nobody", days=7) is False


# ─── Interactions ──────────────────────────────────────────────────────────────

class TestInteractions:
    def test_record_interaction(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        ok = db.record_interaction(acc_id, "targetuser", "LIKE")
        assert ok is True

    def test_check_recent_interaction_true(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        db.record_interaction(acc_id, "targetuser", "LIKE")
        assert db.check_recent_interaction("targetuser", acc_id, days=7) is True

    def test_check_recent_interaction_false_different_account(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        other_id, _ = db.get_or_create_account("otheraccount")
        db.record_interaction(acc_id, "targetuser", "LIKE")
        assert db.check_recent_interaction("targetuser", other_id, days=7) is False

    def test_get_interactions(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        for t in ("user1", "user2", "user3"):
            db.record_interaction(acc_id, t, "FOLLOW")
        interactions = db.get_interactions(acc_id, limit=10)
        assert len(interactions) == 3

    def test_filtered_profile_record_and_check(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        db.record_filtered_profile(
            acc_id, "spammer", "too_few_followers",
            source_type="HASHTAG", source_name="fitness",
        )
        assert db.is_profile_filtered("spammer", acc_id) is True
        assert db.is_profile_filtered("normal", acc_id) is False

    def test_batch_filtered_profiles(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        for name in ("bad1", "bad2"):
            db.record_filtered_profile(
                acc_id, name, "reason", source_type="TARGET", source_name="x"
            )
        filtered = db.check_filtered_profiles_batch(
            ["bad1", "good1", "bad2", "good2"], acc_id
        )
        assert set(filtered) == {"bad1", "bad2"}


# ─── Sessions ─────────────────────────────────────────────────────────────────

class TestSessions:
    def test_create_session(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        sid = db.create_session(acc_id, "Morning run", "TARGET", "@target")
        assert sid is not None
        assert sid > 0

    def test_get_session(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        sid = db.create_session(acc_id, "Morning run", "TARGET", "@target")
        session = db.get_session(sid)
        assert session is not None
        assert session["session_name"] == "Morning run"
        assert session["status"] == "ACTIVE"

    def test_update_session_status(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        sid = db.create_session(acc_id, "run", "TARGET", "@t")
        db.update_session(sid, status="COMPLETED", duration_seconds=120)
        session = db.get_session(sid)
        assert session["status"] == "COMPLETED"
        assert session["duration_seconds"] == 120

    def test_get_sessions_by_account(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        for i in range(3):
            db.create_session(acc_id, f"session_{i}", "TARGET", "@t")
        sessions = db.get_sessions_by_account(acc_id, limit=10)
        assert len(sessions) == 3

    def test_get_session_stats(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        sid = db.create_session(acc_id, "run", "TARGET", "@t")
        db.record_interaction(acc_id, "user1", "LIKE", session_id=sid)
        db.record_interaction(acc_id, "user2", "FOLLOW", session_id=sid)
        stats = db.get_session_stats(sid)
        assert stats["total_interactions"] == 2
        assert stats["total_likes"] == 1
        assert stats["total_follows"] == 1

    def test_create_scraping_session(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        scraping_id = db.create_scraping_session(
            scraping_type="followers",
            source_type="TARGET",
            source_name="@bigaccount",
            max_profiles=200,
            account_id=acc_id,
        )
        assert scraping_id is not None
        session = db.get_scraping_session(scraping_id)
        assert session["scraping_type"] == "followers"
        assert session["source_name"] == "@bigaccount"
        assert session["status"] == "RUNNING"

    def test_complete_scraping_session(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        scraping_id = db.create_scraping_session(
            scraping_type="likers",
            source_type="HASHTAG",
            source_name="fitness",
            account_id=acc_id,
        )
        ok = db.complete_scraping_session(scraping_id, total_scraped=150)
        assert ok is True
        session = db.get_scraping_session(scraping_id)
        assert session["status"] == "COMPLETED"
        assert session["total_scraped"] == 150


# ─── Daily Stats ───────────────────────────────────────────────────────────────

class TestDailyStats:
    def test_daily_stats_incremented_on_interaction(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        db.record_interaction(acc_id, "user1", "LIKE")
        db.record_interaction(acc_id, "user2", "LIKE")
        db.record_interaction(acc_id, "user3", "FOLLOW")
        stats = db.get_account_stats(acc_id, days=1)
        assert stats["total_likes"] == 2
        assert stats["total_follows"] == 1

    def test_unsynced_daily_stats(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_account("botaccount")
        db.record_interaction(acc_id, "user1", "LIKE")
        unsynced = db.get_unsynced_daily_stats()
        assert len(unsynced) >= 1
        ids = [r["id"] for r in unsynced]
        db.mark_daily_stats_synced(ids)
        assert db.get_unsynced_daily_stats() == []
