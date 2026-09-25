"""A confirmed TikTok unfollow is written to the base, and a follow is dated like Instagram dates it.

T2 of the unfollow plan: the TikTok unfollow wrote nothing, so no base could tell an account the
bot had just unfollowed from one still followed, and the day's unfollows were never counted
(`daily_stats_unified.total_unfollows` existed for both platforms, TikTok had no mapping for it).

The follow date: the bot's last FOLLOW, else the first sighting by a following sync; with both,
the younger (a sync reopens the row of an account followed again after an unfollow). Real schema,
temporary base.
"""

import pytest

import taktik.core.database.tiktok_follow_graph as graph_module
from taktik.core.database.tiktok_follow_graph import TikTokFollowGraphService


@pytest.fixture
def base(db, monkeypatch):
    monkeypatch.setattr(graph_module, "get_local_database", lambda: db)
    account_id, _ = db.get_or_create_tiktok_account("moncompte")
    return db, account_id


def test_a_confirmed_unfollow_is_filed_counted_and_closes_the_following_row(base):
    db, account_id = base
    TikTokFollowGraphService.upsert_following("alpha_one", account_id=account_id)

    assert TikTokFollowGraphService.record_unfollow("alpha_one", account_id) is True

    row = db._connection.execute(
        "SELECT COUNT(*) FROM interactions i JOIN social_profiles p ON p.legacy_profile_id = i.profile_id "
        "AND p.platform = i.platform WHERE i.platform = 'tiktok' AND i.account_id = ? "
        "AND i.interaction_type = 'UNFOLLOW' AND p.username = 'alpha_one'",
        (account_id,),
    ).fetchone()
    assert row[0] == 1
    stats = db.get_tiktok_daily_stats(account_id, days=1)
    assert stats[0]["total_unfollows"] == 1
    assert "alpha_one" not in TikTokFollowGraphService.get_active_following_usernames(account_id)


def test_nothing_is_filed_without_an_account_or_a_handle(base):
    _, account_id = base
    assert TikTokFollowGraphService.record_unfollow("", account_id) is False
    assert TikTokFollowGraphService.record_unfollow("alpha_one", 0) is False


def test_a_bot_follow_dates_the_follow(base):
    db, account_id = base
    db.record_tiktok_interaction(account_id, "beta_two", "FOLLOW")

    assert TikTokFollowGraphService.get_follow_age_days("beta_two", account_id) == 0


def test_a_sync_sighting_dates_a_follow_made_by_hand(base):
    db, account_id = base
    TikTokFollowGraphService.upsert_following("by_hand", account_id=account_id)
    db._connection.execute(
        "UPDATE social_graph_sync SET first_seen_at = datetime('now', '-10 days') "
        "WHERE platform = 'tiktok' AND username = 'by_hand'"
    )

    assert TikTokFollowGraphService.get_follow_age_days("by_hand", account_id) == 10


def test_nothing_dates_an_account_neither_followed_by_the_bot_nor_synced(base):
    _, account_id = base
    assert TikTokFollowGraphService.get_follow_age_days("stranger", account_id) is None


def test_with_both_dates_the_younger_wins(base):
    """Followed by the bot long ago, unfollowed, followed again by hand: the sync's reopening dates it."""
    db, account_id = base
    db.record_tiktok_interaction(account_id, "gamma", "FOLLOW")
    db._connection.execute(
        "UPDATE interactions SET interaction_time = datetime('now', '-50 days') "
        "WHERE platform = 'tiktok' AND interaction_type = 'FOLLOW'"
    )
    TikTokFollowGraphService.upsert_following("gamma", account_id=account_id)
    db._connection.execute(
        "UPDATE social_graph_sync SET first_seen_at = datetime('now', '-1 days') "
        "WHERE platform = 'tiktok' AND username = 'gamma'"
    )

    assert TikTokFollowGraphService.get_follow_age_days("gamma", account_id) == 1
