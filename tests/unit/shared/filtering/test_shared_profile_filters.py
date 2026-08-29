"""The shared evaluator must stay indistinguishable from the Instagram one it was lifted from.

Instagram still calls its own `FilteringBusiness`, because switching a live decision path is a
separate, deliberate step. Until it does, only a test keeps the two from drifting: a copy nobody
compares is a fork, and this one decides whether a client's profile is interacted with or skipped.
"""

import itertools

import pytest

from taktik.core.shared.filtering import apply_comprehensive_filter
from taktik.core.social_media.instagram.actions.business.management.filtering import FilteringBusiness


PROFILES = [
    {},
    {"username": "clean", "followers_count": 5000, "following_count": 800, "posts_count": 120,
     "biography": "photographe a Lyon", "full_name": "Marie D", "visible_posts_count": 12},
    {"username": "private", "is_private": True, "followers_count": 900, "posts_count": 40},
    {"username": "huge", "followers_count": 2_000_000, "following_count": 12, "posts_count": 3000,
     "is_verified": True, "visible_posts_count": 9},
    {"username": "empty_shell", "followers_count": 1200, "following_count": 4000,
     "posts_count": 0, "biography": "", "visible_posts_count": 0},
    {"username": "spam", "followers_count": 300, "following_count": 20, "posts_count": 8,
     "biography": "DM me for promo, link in bio", "visible_posts_count": 2,
     "is_business": True, "visible_stories_count": 3},
    {"username": "none_followers", "followers_count": None, "posts_count": 10},
    {"username": "ratio_edge", "followers_count": 1000, "following_count": 100, "posts_count": 50,
     "visible_posts_count": 5},
]

CRITERIA = [
    {},
    {"min_followers": 1000},
    {"min_followers": 1000, "max_followers": 100_000},
    {"allow_private": True, "min_posts": 5},
    {"forbidden_bio_keywords": ["promo", "casino"]},
    {"required_bio_keywords": ["photographe"]},
    {"require_bio": True, "require_full_name": True},
    {"max_following_ratio": 2.0, "verified_penalty": 25, "business_penalty": 40},
    {"min_score": 95},
    {"min_score": 0},
]


@pytest.fixture(scope="module")
def instagram_filter():
    # The class touches neither device nor session on this path; a placeholder is enough to
    # construct it, and if that ever stops being true this fixture is where it will show.
    return FilteringBusiness(device=object(), session_manager=None)


@pytest.mark.parametrize(
    "profile,criteria", list(itertools.product(PROFILES, CRITERIA)),
    ids=lambda value: str(value.get("username", "criteria"))[:24],
)
def test_shared_evaluator_matches_the_instagram_one(instagram_filter, profile, criteria):
    assert apply_comprehensive_filter(profile, criteria) == instagram_filter.apply_comprehensive_filter(
        profile, criteria
    )


def test_no_criteria_lets_a_reasonable_profile_through():
    """Filters ship disabled: an empty criteria dict must reject nobody."""
    verdict = apply_comprehensive_filter(PROFILES[1], {})
    assert verdict["suitable"] is True
    assert verdict["reasons"] == []


def test_the_stages_combine_by_minimum_not_by_sum():
    """Two penalties in different stages leave the score at the worse one, not at their sum."""
    verdict = apply_comprehensive_filter(
        {"username": "two_penalties", "followers_count": 1000, "following_count": 1,
         "posts_count": 0, "biography": "promo", "visible_posts_count": 0},
        {"forbidden_bio_keywords": ["promo"], "min_score": 0},
    )
    # advanced: -20 (low activity) and -30 (ratio) -> 50 ; content: -25 -> 75 ; behavior: -15 -> 85
    assert verdict["score"] == 50


def test_a_score_landing_exactly_on_the_threshold_passes():
    verdict = apply_comprehensive_filter(
        {"username": "borderline", "followers_count": 1000, "following_count": 100,
         "posts_count": 50, "visible_posts_count": 0},
        {"min_score": 85},
    )
    assert verdict["score"] == 85
    assert verdict["suitable"] is True
