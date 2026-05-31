from taktik.core.social_media.tiktok.services.followers.stop_policy import (
    DEFAULT_MAX_CONSECUTIVE_KNOWN_USERNAMES,
    KnownProfilesStopPolicy,
    normalize_username,
)


def test_normalize_username_strips_at_and_lowercases():
    assert normalize_username(" @SomeUser ") == "someuser"


def test_policy_resets_consecutive_known_when_new_username_is_seen():
    policy = KnownProfilesStopPolicy(max_consecutive_known_usernames=2)

    first = policy.observe("known_1", is_known=True)
    new = policy.observe("new_1", is_known=False)

    assert first.consecutive_known_usernames == 1
    assert new.status == "new"
    assert new.consecutive_known_usernames == 0
    assert not new.should_stop


def test_policy_stops_after_configured_consecutive_known_usernames():
    policy = KnownProfilesStopPolicy(max_consecutive_known_usernames=2)

    assert not policy.observe("known_1", is_known=True).should_stop
    decision = policy.observe("known_2", is_known=True)

    assert decision.should_stop
    assert decision.consecutive_known_usernames == 2
    assert decision.max_consecutive_known_usernames == 2


def test_policy_ignores_duplicate_username_without_incrementing_known_streak():
    policy = KnownProfilesStopPolicy(max_consecutive_known_usernames=2)

    assert policy.observe("user_1", is_known=False).status == "new"
    duplicate = policy.observe("@USER_1", is_known=False)

    assert duplicate.status == "duplicate"
    assert duplicate.known_usernames_seen == 0
    assert duplicate.consecutive_known_usernames == 0


def test_policy_counts_unique_known_usernames_only():
    policy = KnownProfilesStopPolicy(max_consecutive_known_usernames=2)

    first = policy.observe("known_1", is_known=True)
    duplicate = policy.observe("known_1", is_known=True)

    assert first.known_usernames_seen == 1
    assert duplicate.status == "duplicate"
    assert duplicate.known_usernames_seen == 1
    assert duplicate.consecutive_known_usernames == 1
    assert not duplicate.should_stop


def test_policy_ignores_empty_usernames_without_incrementing_counters():
    policy = KnownProfilesStopPolicy(max_consecutive_known_usernames=2)

    decision = policy.observe("", is_known=True)

    assert decision.status == "ignored"
    assert decision.total_observations == 0
    assert decision.unique_usernames_seen == 0


def test_policy_falls_back_to_default_when_limit_is_invalid():
    policy = KnownProfilesStopPolicy(max_consecutive_known_usernames=None)

    assert policy.max_consecutive_known_usernames == DEFAULT_MAX_CONSECUTIVE_KNOWN_USERNAMES
