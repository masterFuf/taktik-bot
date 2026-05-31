from taktik.core.social_media.tiktok.services.followers.scroll_policy import (
    calculate_legacy_followers_scroll_attempts,
    get_visited_ratio,
)


def test_scroll_policy_uses_ratio_when_target_total_is_known():
    decision = calculate_legacy_followers_scroll_attempts(
        target_followers_count=100,
        already_visited_count=20,
        profiles_visited=35,
    )

    assert decision.attempts == 15
    assert decision.total_visited == 55
    assert decision.reason == "ratio_50"


def test_scroll_policy_uses_low_attempts_near_end_of_known_target():
    decision = calculate_legacy_followers_scroll_attempts(
        target_followers_count=100,
        already_visited_count=80,
        profiles_visited=10,
    )

    assert decision.attempts == 5
    assert decision.reason == "ratio_90"


def test_scroll_policy_uses_visited_count_when_target_total_is_unknown():
    decision = calculate_legacy_followers_scroll_attempts(
        target_followers_count=0,
        already_visited_count=60,
        profiles_visited=0,
    )

    assert decision.attempts == 10
    assert decision.reason == "visited_lt_100"


def test_scroll_policy_uses_default_when_no_data_is_available():
    decision = calculate_legacy_followers_scroll_attempts(
        target_followers_count=0,
        already_visited_count=0,
        profiles_visited=0,
    )

    assert decision.attempts == 3
    assert decision.reason == "no_data"


def test_get_visited_ratio_caps_at_one_and_returns_zero_when_unknown():
    assert get_visited_ratio(
        target_followers_count=100,
        already_visited_count=90,
        profiles_visited=20,
    ) == 1.0
    assert get_visited_ratio(
        target_followers_count=0,
        already_visited_count=90,
        profiles_visited=20,
    ) == 0.0
