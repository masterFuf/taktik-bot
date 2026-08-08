"""The private-zone escape settings must survive the desktop -> action config trip.

The workflow reads its policy from the ACTION's filter block, not from the top-level
``built["filters"]``. A key missing from `_build_action_config` is therefore not a visible
failure: the policy silently falls back to its dataclass defaults and the operator's choice
is discarded — the exact trap the surrounding code comments already document for the profile
bounds and the revisit delays.

Two keys, two distinct reasons:
  - ``allow_private`` DISARMS the mechanism. Lost in transit, the bot would keep jumping for
    an operator who accepts private profiles, skipping perfectly valid targets.
  - ``max_consecutive_private_profiles`` is the threshold itself.
"""

from taktik.core.social_media.instagram.workflows.core.config_builder import _build_action_config
from taktik.core.social_media.instagram.actions.business.workflows.common.private_streak_policy import (
    PrivateStreakPolicy,
)


def _action_filters(raw_filters):
    """Only the filter block matters here; the rest is the minimum the builder requires."""
    action = _build_action_config(
        raw_config={"filters": raw_filters},
        action_type="interact_with_followers",
        interaction_type="followers",
        primary_target="someone",
        target_list=["someone"],
        max_profiles=10,
        min_likes_per_profile=1,
        max_likes_per_profile=3,
        like_percentage=80,
        follow_percentage=20,
        comment_percentage=0,
        story_percentage=0,
        story_like_percentage=0,
    )
    return action["filters"]


class TestPrivateStreakConfigTravel:
    def test_threshold_reaches_the_action(self):
        filters = _action_filters({"allowPrivate": False, "maxConsecutivePrivateProfiles": 8})
        assert filters["max_consecutive_private_profiles"] == 8
        assert PrivateStreakPolicy.from_filters(filters).threshold == 8

    def test_allow_private_reaches_the_action_and_disarms(self):
        filters = _action_filters({"allowPrivate": True})
        assert filters["allow_private"] is True
        assert not PrivateStreakPolicy.from_filters(filters).enabled

    def test_rejecting_private_profiles_arms_the_mechanism(self):
        filters = _action_filters({"allowPrivate": False})
        assert filters["allow_private"] is False
        assert PrivateStreakPolicy.from_filters(filters).enabled

    def test_never_travels_as_never(self):
        """0 is the operator's "never" — it must not be read as "missing" and defaulted."""
        filters = _action_filters({"allowPrivate": False, "maxConsecutivePrivateProfiles": 0})
        assert not PrivateStreakPolicy.from_filters(filters).enabled

    def test_absent_settings_leave_standalone_behaviour_unchanged(self):
        """A standalone run sends no such keys and must still get sane defaults."""
        policy = PrivateStreakPolicy.from_filters(_action_filters({}))
        assert policy.enabled
