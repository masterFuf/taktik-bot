"""The private-zone escape decides WHEN to jump and HOW FAR — nothing else.

These lock the three properties that make the mechanism safe rather than clever: it stays
off unless the operator rejects private profiles, it never runs forever, and it never
flings past the end of a short list.
"""

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.common.private_streak_policy import (
    DEFAULT_BASE_FLINGS,
    DEFAULT_MAX_JUMPS,
    DEFAULT_THRESHOLD,
    PrivateStreakPolicy,
)


class TestArming:
    def test_disabled_when_private_profiles_are_allowed(self):
        """No rejection means no poisoned zone: jumping would only skip valid targets."""
        policy = PrivateStreakPolicy.from_filters({"allow_private": True})
        assert not policy.enabled
        assert not policy.should_escape(private_streak=99, jumps_done=0)

    def test_camelcase_allow_private_is_honoured(self):
        """The desktop sends camelCase; the bot must not silently arm the mechanism."""
        assert not PrivateStreakPolicy.from_filters({"allowPrivate": True}).enabled

    def test_enabled_by_default_when_private_profiles_are_rejected(self):
        policy = PrivateStreakPolicy.from_filters({"allow_private": False})
        assert policy.enabled
        assert policy.threshold == DEFAULT_THRESHOLD

    @pytest.mark.parametrize("never", [0, -1, "0"])
    def test_zero_or_negative_means_never(self, never):
        policy = PrivateStreakPolicy.from_filters({"max_consecutive_private_profiles": never})
        assert not policy.enabled

    def test_unreadable_value_falls_back_rather_than_arming_wildly(self):
        policy = PrivateStreakPolicy.from_filters({"max_consecutive_private_profiles": "abc"})
        assert policy.threshold == DEFAULT_THRESHOLD


class TestShouldEscape:
    def test_waits_for_the_full_streak(self):
        policy = PrivateStreakPolicy(threshold=5)
        assert not policy.should_escape(private_streak=4, jumps_done=0)
        assert policy.should_escape(private_streak=5, jumps_done=0)

    def test_stops_after_the_jump_ceiling(self):
        """Past the ceiling the whole list is poisoned; insisting is the acharnement that
        would read as a bot, and the run must keep producing rather than keep jumping."""
        policy = PrivateStreakPolicy(threshold=5, max_jumps=DEFAULT_MAX_JUMPS)
        assert policy.should_escape(private_streak=10, jumps_done=DEFAULT_MAX_JUMPS - 1)
        assert not policy.should_escape(private_streak=10, jumps_done=DEFAULT_MAX_JUMPS)


class TestAmplitude:
    def test_doubles_on_each_successive_jump(self):
        policy = PrivateStreakPolicy(base_flings=DEFAULT_BASE_FLINGS)
        # Jitter is ±25%, so compare bands rather than exact values.
        first = [policy.flings_for_jump(0) for _ in range(60)]
        second = [policy.flings_for_jump(1) for _ in range(60)]
        assert max(first) < min(second), "a second jump must always reach further than a first"

    def test_never_flings_past_a_short_list(self):
        """84 followers: a second jump of 12 flings would only land at the bottom."""
        policy = PrivateStreakPolicy(base_flings=DEFAULT_BASE_FLINGS)
        for _ in range(60):
            assert policy.flings_for_jump(jumps_done=2, source_followers=84) <= 9

    def test_unknown_source_size_does_not_cap(self):
        policy = PrivateStreakPolicy(base_flings=DEFAULT_BASE_FLINGS)
        assert policy.flings_for_jump(0, source_followers=None) >= 1

    def test_always_at_least_one_gesture(self):
        policy = PrivateStreakPolicy(base_flings=1)
        assert policy.flings_for_jump(0, source_followers=1) >= 1

    def test_amplitude_varies_so_the_rescue_is_not_a_signature(self):
        policy = PrivateStreakPolicy(base_flings=DEFAULT_BASE_FLINGS)
        seen = {policy.flings_for_jump(0) for _ in range(60)}
        assert len(seen) > 1, "a fixed amplitude at a fixed trigger is a detectable pattern"
