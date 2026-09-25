"""The one reading of a Followers payload: targets, budgets, units by vocabulary, defaults."""
from dataclasses import asdict

import pytest

from taktik.core.social_media.tiktok.actions.business.workflows.followers.models import FollowersConfig
from taktik.core.social_media.tiktok.actions.business.workflows.followers.payload import (
    DEFAULT_PROFILE_BUDGET,
    followers_config_for_target,
    followers_settings_from_payload,
    followers_targets_from_payload,
    names_a_target_list,
    profile_budget_from_payload,
    profile_budgets,
    session_limits_from_payload,
)


def _config(payload, **overrides):
    likes, follows = session_limits_from_payload(payload)
    budget = {"search_query": "x", "max_followers": 1, "max_likes_per_session": likes,
              "max_follows_per_session": follows, **overrides}
    return followers_config_for_target(followers_settings_from_payload(payload), **budget)


def test_an_empty_payload_gives_the_workflow_defaults_but_the_follows_budget():
    """The dataclass says 30 follows; every reader of a payload always said 20."""
    expected = asdict(FollowersConfig(search_query="x", max_followers=1, max_follows_per_session=20))
    assert asdict(_config({})) == expected


@pytest.mark.parametrize("payload, expected", [
    ({"targetAccounts": ["@a", "b"], "targets": ["c"], "searchQuery": "d"}, ["a", "b"]),
    ({"targets": ["c", " @d "], "searchQuery": "e"}, ["c", "d"]),
    ({"targets": "solo"}, ["solo"]),
    ({"searchQuery": "@e"}, ["e"]),
    ({"search_query": "f"}, ["f"]),
    ({"target": "g"}, ["g"]),
    ({"username": "h"}, ["h"]),
    ({"targets": ["  ", "@"], "searchQuery": "e"}, []),
    ({"searchQuery": "  "}, []),
    ({}, []),
])
def test_the_targets_are_the_list_first_then_the_single_target(payload, expected):
    assert followers_targets_from_payload(payload) == expected


def test_a_list_without_a_usable_name_is_told_apart_from_no_list():
    assert names_a_target_list({"targets": ["  "]}) is True
    assert names_a_target_list({"searchQuery": "a"}) is False


@pytest.mark.parametrize("payload, expected", [
    ({"maxFollowers": 3, "maxVideos": 9}, 3),
    ({"max_followers": 4}, 4),
    ({"maxVideos": 9}, 9),
    ({"maxFollowers": 0, "maxVideos": 0}, 0),
    ({}, DEFAULT_PROFILE_BUDGET),
])
def test_the_profile_budget_is_max_followers_then_max_videos(payload, expected):
    assert profile_budget_from_payload(payload) == expected


@pytest.mark.parametrize("total, count, expected", [
    (3, 2, [2, 1]),
    (5, 3, [2, 2, 1]),
    (6, 3, [2, 2, 2]),
    (20, 1, [20]),
    # Below the number of targets, the last ones get nothing (the bridge gave each one at least 1).
    (1, 2, [1, 0]),
    (2, 3, [1, 1, 0]),
    (0, 2, [0, 0]),
])
def test_the_budget_is_shared_the_first_targets_taking_the_remainder(total, count, expected):
    assert profile_budgets(total, count) == expected
    assert sum(profile_budgets(total, count)) == total


@pytest.mark.parametrize("payload, expected", [
    ({"likeProbability": 1}, 0.01),
    ({"likeProbability": 0}, 0.0),
    ({"like_probability": 0.25}, 0.25),
    ({"like_probability": 25}, 0.25),
    ({}, 0.7),
])
def test_a_probability_is_read_in_the_unit_of_its_vocabulary(payload, expected):
    assert _config(payload).like_probability == pytest.approx(expected)


def test_the_page_keys_the_cli_used_to_drop_are_read():
    config = _config({"commentProbability": 20, "commentTexts": ["Nice one"], "storyLikeProbability": 0})

    assert config.comment_probability == pytest.approx(0.2)
    assert config.comment_texts == ["Nice one"]
    assert config.story_like_probability == 0.0


def test_skip_private_accounts_is_a_filter_criterion_not_a_setting():
    config = _config({"skipPrivateAccounts": True})

    assert config.skip_private_accounts is False
    assert config.filters["allow_private"] is False
