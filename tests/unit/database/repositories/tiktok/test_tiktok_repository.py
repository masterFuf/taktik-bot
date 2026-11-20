"""Unit tests for the TikTok SQLite repository."""

import json

from taktik.core.database.repositories.tiktok.tiktok_repository import TikTokRepository


def test_profile_update_keeps_existing_counts_when_new_value_is_zero(conn):
    repo = TikTokRepository(conn)

    profile_id, created = repo.get_or_create_profile("creator", followers_count=1000)
    assert created is True

    same_profile_id, created = repo.get_or_create_profile("creator", followers_count=0)
    assert same_profile_id == profile_id
    assert created is False

    profile = repo.find_profile_by_username("creator")
    assert profile["followers_count"] == 1000


def test_create_session_redacts_config_and_truncates_public_fields(conn):
    repo = TikTokRepository(conn)
    account_id, _ = repo.get_or_create_account("bot")

    session_id = repo.create_session(
        account_id=account_id,
        session_name="x" * 120,
        workflow_type="TARGET",
        target="target_" + ("y" * 80),
        config_used={"api_key": "secret", "safe": "value"},
    )

    session = repo.get_session_stats(session_id)
    assert len(session["session_name"]) == 100
    assert len(session["target"]) == 50
    assert json.loads(session["config_used"]) == {
        "api_key": "***REDACTED***",
        "safe": "value",
    }


def test_record_interaction_for_username_updates_daily_stats(conn):
    repo = TikTokRepository(conn)
    account_id, _ = repo.get_or_create_account("bot")

    assert repo.record_interaction_for_username(account_id, "creator1", "LIKE") is True
    assert repo.record_interaction_for_username(account_id, "creator2", "FOLLOW") is True

    interactions = repo.get_interactions(account_id)
    assert {row["target_username"] for row in interactions} == {"creator1", "creator2"}

    stats = repo.get_daily_stats(account_id, days=1)
    assert len(stats) == 1
    assert stats[0]["total_likes"] == 1
    assert stats[0]["total_follows"] == 1


def test_a_new_profile_keeps_a_counter_not_given_unknown(conn):
    # A row created from a list (a handle and nothing read) or with a counter not read stays NULL.
    repo = TikTokRepository(conn)

    repo.get_or_create_profile("listed_only")
    repo.get_or_create_profile("half_read", followers_count=None, following_count=12)

    listed = repo.find_profile_by_username("listed_only")
    half = repo.find_profile_by_username("half_read")
    assert (listed["followers_count"], listed["following_count"], listed["likes_count"]) == (None, None, None)
    assert (half["followers_count"], half["following_count"]) == (None, 12)
