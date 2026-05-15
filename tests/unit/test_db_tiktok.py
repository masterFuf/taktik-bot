"""Unit tests for TikTok-specific DB operations in LocalDatabaseService."""
import pytest
from taktik.core.database.local.service import LocalDatabaseService


class TestTikTokAccounts:
    def test_create_tiktok_account(self, db: LocalDatabaseService):
        acc_id, created = db.get_or_create_tiktok_account("tiktokbot")
        assert created is True
        assert acc_id > 0

    def test_idempotent_create(self, db: LocalDatabaseService):
        acc_id1, _ = db.get_or_create_tiktok_account("tiktokbot")
        acc_id2, created = db.get_or_create_tiktok_account("tiktokbot")
        assert created is False
        assert acc_id1 == acc_id2

    def test_get_by_username(self, db: LocalDatabaseService):
        db.get_or_create_tiktok_account("ttuser", display_name="TT User")
        acc = db.get_tiktok_account_by_username("ttuser")
        assert acc is not None
        assert acc["username"] == "ttuser"

    def test_unknown_returns_none(self, db: LocalDatabaseService):
        assert db.get_tiktok_account_by_username("ghost") is None


class TestTikTokProfiles:
    def test_create_profile(self, db: LocalDatabaseService):
        pid, created = db.get_or_create_tiktok_profile({"username": "creator1"})
        assert created is True
        assert pid > 0

    def test_upsert_updates_stats(self, db: LocalDatabaseService):
        db.get_or_create_tiktok_profile({"username": "creator1", "followers_count": 100})
        pid2, created = db.get_or_create_tiktok_profile({
            "username": "creator1",
            "followers_count": 5000,
        })
        assert created is False
        profile = db.get_tiktok_profile_by_username("creator1")
        assert profile["followers_count"] == 5000

    def test_get_by_username(self, db: LocalDatabaseService):
        db.get_or_create_tiktok_profile({"username": "creator2", "biography": "Bio here"})
        profile = db.get_tiktok_profile_by_username("creator2")
        assert profile is not None
        assert profile["biography"] == "Bio here"


class TestTikTokSessions:
    def test_create_session(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_tiktok_account("tiktokbot")
        sid = db.create_tiktok_session(acc_id, "Hashtag run", "HASHTAG", target="#dance")
        assert sid is not None
        assert sid > 0

    def test_update_session(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_tiktok_account("tiktokbot")
        sid = db.create_tiktok_session(acc_id, "run", "TARGET", target="bigcreator")
        ok = db.update_tiktok_session(sid, likes=10, follows=5, status="COMPLETED")
        assert ok is True
        sessions = db.get_tiktok_sessions(account_id=acc_id, limit=5)
        assert len(sessions) == 1
        assert sessions[0]["status"] == "COMPLETED"

    def test_end_session(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_tiktok_account("tiktokbot")
        sid = db.create_tiktok_session(acc_id, "run", "TARGET")
        ok = db.end_tiktok_session(sid, status="COMPLETED", stats={"likes": 20, "follows": 5})
        assert ok is True
        sessions = db.get_tiktok_sessions(account_id=acc_id)
        assert sessions[0]["likes"] == 20


class TestTikTokInteractions:
    def test_record_interaction(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_tiktok_account("tiktokbot")
        ok = db.record_tiktok_interaction(acc_id, "creator1", "LIKE")
        assert ok is True

    def test_check_recent_interaction(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_tiktok_account("tiktokbot")
        db.record_tiktok_interaction(acc_id, "creator1", "FOLLOW")
        assert db.check_tiktok_recent_interaction("creator1", acc_id, hours=168) is True

    def test_check_recent_interaction_unknown(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_tiktok_account("tiktokbot")
        assert db.check_tiktok_recent_interaction("nobody", acc_id, hours=168) is False

    def test_has_tiktok_interaction_alias(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_tiktok_account("tiktokbot")
        db.record_tiktok_interaction(acc_id, "creator2", "LIKE")
        assert db.has_tiktok_interaction(acc_id, "creator2") is True
        assert db.has_tiktok_interaction(acc_id, "nobody") is False

    def test_filtered_tiktok_profile(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_tiktok_account("tiktokbot")
        db.record_tiktok_filtered_profile(
            acc_id, "spammer", "private_account",
            source_type="HASHTAG", source_name="dance",
        )
        assert db.is_tiktok_profile_filtered("spammer", acc_id) is True
        assert db.is_tiktok_profile_filtered("clean", acc_id) is False

    def test_tiktok_daily_stats(self, db: LocalDatabaseService):
        acc_id, _ = db.get_or_create_tiktok_account("tiktokbot")
        db.record_tiktok_interaction(acc_id, "c1", "LIKE")
        db.record_tiktok_interaction(acc_id, "c2", "LIKE")
        db.record_tiktok_interaction(acc_id, "c3", "FOLLOW")
        stats = db.get_tiktok_daily_stats(acc_id, days=1)
        assert len(stats) == 1
        assert stats[0]["total_likes"] == 2
        assert stats[0]["total_follows"] == 1
