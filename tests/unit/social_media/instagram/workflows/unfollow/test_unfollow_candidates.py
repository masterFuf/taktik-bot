"""U2: the candidates come from the base, rule by rule, and in doubt nobody is unfollowed."""

from datetime import datetime, timedelta

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.unfollow.candidates import (
    FollowersSnapshot,
    FollowingRecord,
    select_candidates,
)

NOW = datetime(2026, 9, 24, 12, 0, 0)


def _bot(name, days_ago):
    return FollowingRecord(name, followed_by_bot=True, followed_at=NOW - timedelta(days=days_ago))


def _manual(name, days_ago=None):
    seen = None if days_ago is None else NOW - timedelta(days=days_ago)
    return FollowingRecord(name, followed_by_bot=False, first_seen_at=seen)


def _cfg(**over):
    base = {"unfollow_mode": "non-followers", "bot_follows_only": True, "min_days_since_follow": 3,
            "whitelist": [], "blacklist": []}
    base.update(over)
    return base


COMPLETE = FollowersSnapshot(frozenset({"fan_mutual"}), complete=True)


def test_non_followers_takes_only_accounts_known_not_to_follow_back():
    records = [_bot("ghost", 10), _bot("fan_mutual", 10)]
    selection = select_candidates(records, _cfg(), COMPLETE, NOW)
    assert selection.candidates == ["ghost"]
    assert selection.refusals == {"follows_back": 1}


def test_non_followers_without_a_complete_followers_sync_unfollows_nobody():
    records = [_bot("ghost", 10), _bot("other", 20)]
    partial = FollowersSnapshot(frozenset({"someone"}), complete=False)
    assert select_candidates(records, _cfg(), partial, NOW).candidates == []
    assert select_candidates(records, _cfg(), None, NOW).refusals == {"reciprocity_unknown": 2}


def test_mutual_takes_only_accounts_seen_following_back():
    records = [_bot("ghost", 10), _bot("fan_mutual", 10)]
    assert select_candidates(records, _cfg(unfollow_mode="mutual"), COMPLETE, NOW).candidates == ["fan_mutual"]


def test_mutual_trusts_a_partial_list_only_for_who_it_saw():
    partial = FollowersSnapshot(frozenset({"fan_mutual"}), complete=False)
    selection = select_candidates([_bot("ghost", 10), _bot("fan_mutual", 10)],
                                  _cfg(unfollow_mode="mutual"), partial, NOW)
    assert selection.candidates == ["fan_mutual"]
    assert selection.refusals == {"reciprocity_unknown": 1}


@pytest.mark.parametrize("mode", ["oldest", "all"])
def test_oldest_and_all_ignore_reciprocity_and_go_oldest_first(mode):
    records = [_bot("recent", 5), _bot("fan_mutual", 30), _bot("old", 60)]
    assert select_candidates(records, _cfg(unfollow_mode=mode), None, NOW).candidates == [
        "old", "fan_mutual", "recent"]


def test_the_whitelist_wins_over_everything_even_the_blacklist():
    records = [_bot("friend", 100), _manual("friend2", 100)]
    selection = select_candidates(records, _cfg(unfollow_mode="all", whitelist=["@Friend"],
                                                 blacklist=["friend"]), None, NOW)
    assert "friend" not in selection.candidates
    assert selection.refusals["whitelisted"] == 1


def test_the_blacklist_forces_the_unfollow_over_the_other_rules_and_comes_first():
    """The page: 'Ces comptes seront toujours unfollowés (priorité sur les règles)'."""
    records = [_bot("ghost", 10), _manual("spammer", None), _bot("fan_mutual", 10)]
    selection = select_candidates(records, _cfg(blacklist=["SPAMMER", "fan_mutual"]), COMPLETE, NOW)
    # Forced first (undated before dated), then the rule-chosen ones.
    assert selection.candidates == ["spammer", "fan_mutual", "ghost"]


def test_manual_follows_are_protected_by_default():
    selection = select_candidates([_manual("my_friend", 400)], _cfg(unfollow_mode="all"), None, NOW)
    assert selection.candidates == []
    assert selection.refusals == {"not_followed_by_bot": 1}


def test_manual_follows_can_be_included_when_the_user_says_so():
    selection = select_candidates([_manual("old_manual", 400)],
                                  _cfg(unfollow_mode="all", bot_follows_only=False), None, NOW)
    assert selection.candidates == ["old_manual"]


def test_the_minimum_delay_since_the_follow_is_respected():
    records = [_bot("two_days", 2), _bot("three_days", 3.01)]
    selection = select_candidates(records, _cfg(unfollow_mode="all"), None, NOW)
    assert selection.candidates == ["three_days"]
    assert selection.refusals == {"followed_too_recently": 1}


def test_an_unknown_follow_date_waits_when_a_delay_is_set():
    selection = select_candidates([_manual("undated")],
                                  _cfg(unfollow_mode="all", bot_follows_only=False), None, NOW)
    assert selection.candidates == []
    assert selection.refusals == {"follow_date_unknown": 1}


def test_no_delay_lets_an_undated_follow_through():
    selection = select_candidates([_manual("undated")],
                                  _cfg(unfollow_mode="all", bot_follows_only=False,
                                       min_days_since_follow=0), None, NOW)
    assert selection.candidates == ["undated"]


def test_an_unknown_mode_unfollows_nobody():
    selection = select_candidates([_bot("ghost", 10)], _cfg(unfollow_mode="everyone"), COMPLETE, NOW)
    assert selection.candidates == [] and selection.refusals == {"unknown_mode": 1}


def test_rows_become_records_with_bot_ownership_from_the_follow_date():
    from taktik.core.social_media.instagram.actions.business.workflows.unfollow.candidates import records_from_rows

    records = records_from_rows([
        {"username": "a", "last_bot_follow_at": "2026-09-10T08:00:00", "first_seen_at": "2026-09-11 09:00:00"},
        {"username": "b", "last_bot_follow_at": None, "first_seen_at": "2026-09-01 10:00:00"},
        {"username": "c", "last_bot_follow_at": "garbage", "first_seen_at": None},
    ])
    assert [(r.username, r.followed_by_bot) for r in records] == [("a", True), ("b", False), ("c", False)]
    assert records[0].followed_at == datetime(2026, 9, 10, 8, 0, 0)
    assert records[1].first_seen_at == datetime(2026, 9, 1, 10, 0, 0)
    assert records[2].followed_at is None and records[2].first_seen_at is None


# ── Empty settings mean the safe default (review of 2026-09-24) ─────────────────

@pytest.mark.parametrize("empty", [None, ""])
def test_an_empty_bot_follows_only_still_protects_manual_follows(empty):
    selection = select_candidates([_manual("by_hand", 30)],
                                  _cfg(unfollow_mode="all", bot_follows_only=empty), None, NOW)
    assert selection.candidates == [] and selection.refusals == {"not_followed_by_bot": 1}


@pytest.mark.parametrize("empty", [None, ""])
def test_an_empty_delay_is_the_default_three_days(empty):
    records = [_bot("yesterday", 1), _bot("last_week", 7)]
    selection = select_candidates(records, _cfg(unfollow_mode="all", min_days_since_follow=empty), None, NOW)
    assert selection.candidates == ["last_week"]
    assert selection.refusals == {"followed_too_recently": 1}


def test_a_follow_date_with_an_offset_is_read_in_utc():
    from taktik.core.social_media.instagram.actions.business.workflows.unfollow.candidates import records_from_rows

    # 10:00 at UTC-05:00 is 15:00 UTC; the offset used to be dropped, leaving 10:00.
    record = records_from_rows([{"username": "late", "last_bot_follow_at": "2026-09-20T10:00:00-05:00"}])[0]
    assert record.followed_at == datetime(2026, 9, 20, 15, 0, 0)
