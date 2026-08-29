"""TikTok now filters, and must not filter when nobody asked it to."""

import pytest

from taktik.core.social_media.tiktok.actions.business.workflows.followers.filtering import (
    evaluate_tiktok_profile,
    resolve_tiktok_filter_criteria,
    tiktok_profile_for_filtering,
)


EXTRACTED = {
    "username": "creator",
    "display_name": "Marie D",
    "followers_count": 4200,
    "following_count": 300,
    "likes_count": 90_000,
    "videos_count": 60,
    "biography": "photographe a Lyon",
    "is_private": False,
    "is_verified": False,
}


def test_no_criteria_filters_nobody():
    assert evaluate_tiktok_profile(EXTRACTED, {})["suitable"] is True
    assert evaluate_tiktok_profile({"username": "empty"}, {})["suitable"] is True


def test_criteria_are_read_in_either_casing():
    assert resolve_tiktok_filter_criteria({"filters": {"minFollowers": 1000}}) == {"min_followers": 1000}
    assert resolve_tiktok_filter_criteria({"min_followers": 1000}) == {"min_followers": 1000}
    assert resolve_tiktok_filter_criteria({"filters": {"minVideos": 5}}) == {"min_posts": 5}
    assert resolve_tiktok_filter_criteria({}) == {}
    assert resolve_tiktok_filter_criteria(None) == {}


def test_an_empty_criterion_is_not_a_constraint():
    """A UI sending a cleared field must not be read as "minimum zero followers, filter on"."""
    assert resolve_tiktok_filter_criteria({"filters": {"minFollowers": None, "maxFollowers": ""}}) == {}


def test_the_video_count_is_read_as_the_post_count():
    """Feeding TikTok's own field names would cost every profile 35 points for nothing."""
    mapped = tiktok_profile_for_filtering(EXTRACTED)
    assert mapped["posts_count"] == 60
    assert mapped["visible_posts_count"] == 60
    assert mapped["full_name"] == "Marie D"
    assert mapped["biography"] == "photographe a Lyon"

    verdict = evaluate_tiktok_profile(EXTRACTED, {"min_followers": 1000})
    assert verdict["suitable"] is True
    assert "Very low posting activity" not in verdict["reasons"]
    assert "No visible posts" not in verdict["reasons"]


def test_a_profile_below_the_follower_floor_is_rejected():
    verdict = evaluate_tiktok_profile({**EXTRACTED, "followers_count": 40}, {"min_followers": 1000})
    assert verdict["suitable"] is False
    assert verdict["reasons"] == ["Too few followers (40 < 1000)"]


def test_a_private_profile_is_rejected_unless_allowed():
    private = {**EXTRACTED, "is_private": True}
    assert evaluate_tiktok_profile(private, {"min_followers": 1})["suitable"] is False
    assert evaluate_tiktok_profile(private, {"allow_private": True, "min_followers": 1})["suitable"] is True


def test_skip_private_accounts_finally_does_something():
    """The knob was parsed, stored and read by nobody; it now reaches the evaluator."""
    criteria = resolve_tiktok_filter_criteria({"skipPrivateAccounts": True})
    assert criteria == {"allow_private": False}
    assert evaluate_tiktok_profile({**EXTRACTED, "is_private": True}, criteria)["suitable"] is False

    # False means "not asked", never "let private accounts through": it must not switch
    # filtering on by itself.
    assert resolve_tiktok_filter_criteria({"skipPrivateAccounts": False}) == {}


def test_a_business_flag_is_never_invented():
    """TikTok's profile screen carries no business flag; absent must not read as "not a business"."""
    assert "is_business" not in tiktok_profile_for_filtering(EXTRACTED)


class FakeRepository:
    def __init__(self):
        self.filtered = []

    def record_filtered_profile(self, **kwargs):
        self.filtered.append(kwargs)
        return True


class _Workflow:
    """Only the pieces `_filter_current_profile` touches, so the check can be tested alone."""

    from taktik.core.social_media.tiktok.actions.business.workflows.followers.workflow import (
        FollowersWorkflow as _Source,
    )

    _filter_current_profile = _Source._filter_current_profile
    # Taken from the real class rather than restated, so the attribution below stays a check on
    # what the workflow actually does. Both are overridden by the target-profiles workflow.
    FILTER_SOURCE_TYPE = _Source.FILTER_SOURCE_TYPE
    _filter_source_name = _Source._filter_source_name

    def __init__(self, criteria):
        from types import SimpleNamespace

        from loguru import logger

        self.config = SimpleNamespace(filters=criteria, search_query="target")
        self.stats = SimpleNamespace(profiles_filtered=0)
        self.logger = logger
        self._followers_repository = FakeRepository()
        self._account_id = 7
        self._session_id = 42
        self._current_profile_username = "creator"
        self.actions = []

    def _send_stats_update(self):
        self.actions.append("stats")

    def _send_action(self, action, target=""):
        self.actions.append((action, target))


def test_a_rejection_is_recorded_so_the_next_pass_does_not_revisit():
    workflow = _Workflow({"min_followers": 1000})
    assert workflow._filter_current_profile({**EXTRACTED, "followers_count": 40}) is True
    assert workflow.stats.profiles_filtered == 1
    assert workflow._followers_repository.filtered == [
        {
            "account_id": 7,
            "username": "creator",
            "reason": "Too few followers (40 < 1000)",
            "source_type": "followers",
            "source_name": "target",
            "session_id": 42,
        }
    ]
    assert ("filter", "creator") in workflow.actions


def test_an_unreadable_profile_is_not_a_rejection():
    """A device that read nothing is not a verdict; recording one would discard a good profile."""
    workflow = _Workflow({"min_followers": 1000})
    assert workflow._filter_current_profile(None) is False
    assert workflow._followers_repository.filtered == []


def test_without_criteria_the_check_costs_one_test_and_records_nothing():
    workflow = _Workflow({})
    assert workflow._filter_current_profile({**EXTRACTED, "followers_count": 1}) is False
    assert workflow._followers_repository.filtered == []
    assert workflow.stats.profiles_filtered == 0
