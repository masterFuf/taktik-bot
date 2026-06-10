"""Workflow-test config builder honours the real prod config surface.

The Cartography Lab workflow test must mirror the real workflows: when the front
sends profile filters / likes / consecutive-known, the harness must apply them
verbatim (not a permissive stub), so a test run selects the same profiles as prod.
"""

from bridges.compat.diagnostics.runtime.workflow_test.platforms.instagram.automation_config import (
    build_workflow_config,
)


def _base_limits():
    return {"maxProfiles": 30, "minLikesPerProfile": 1, "maxLikesPerProfile": 3}


def _base_probs():
    return {"like": 70, "follow": 15, "comment": 5, "watchStories": 10, "likeStories": 30}


def test_filters_are_applied_verbatim():
    filters = {
        "minFollowers": 100,
        "maxFollowers": 50000,
        "minPosts": 3,
        "maxFollowing": 7500,
        "allowPrivate": False,
        "allowVerified": True,
        "allowBusiness": False,
    }
    cfg = build_workflow_config(
        "target_followers", "natgeo", _base_limits(), _base_probs(),
        session_duration=60, delays={"min": 5, "max": 15},
        filters=filters, max_consecutive_known=150,
    )
    f = cfg["filters"]
    assert f["min_followers"] == 100
    assert f["max_followers"] == 50000
    assert f["min_posts"] == 3
    assert f["max_followings"] == 7500
    # allowPrivate False → public-only relation + allow flag preserved for criteria.
    assert f["privacy_relation"] == "public"
    assert f["allow_private"] is False
    assert f["allow_verified"] is True
    assert f["allow_business"] is False


def test_session_carries_likes_and_consecutive_known():
    cfg = build_workflow_config(
        "target_followers", "natgeo", _base_limits(), _base_probs(),
        session_duration=60, filters=None, max_consecutive_known=150,
    )
    assert cfg["session_settings"]["max_consecutive_known_usernames"] == 150
    assert cfg["session_settings"]["session_duration_minutes"] == 60
    action = cfg["actions"][0]
    assert action["min_likes_per_profile"] == 1
    assert action["max_likes_per_profile"] == 3


def test_omitting_filters_keeps_permissive_defaults():
    cfg = build_workflow_config(
        "target_followers", "natgeo", _base_limits(), _base_probs(),
    )
    f = cfg["filters"]
    assert f["min_followers"] == 0
    assert f["privacy_relation"] == "public_and_private"
    # No consecutive-known cap when not supplied.
    assert "max_consecutive_known_usernames" not in cfg["session_settings"]


def test_rhythm_driven_omits_explicit_delays_and_passes_behavior_policy():
    """No explicit delays + a behaviorPolicy => the pacing profile drives the rhythm.

    Mirrors the redesigned Instagram config surface (Lot 4): the SessionManager then
    derives the between-actions delay from the profile instead of a fixed window.
    """
    cfg = build_workflow_config(
        "target_followers", "natgeo", _base_limits(), _base_probs(),
        session_duration=60, delays=None,
        behavior_policy={"profileId": "fast"},
    )
    assert "delay_between_actions" not in cfg["session_settings"]
    assert cfg["behaviorPolicy"] == {"profileId": "fast"}


def test_explicit_delays_win_and_behavior_policy_passes_through():
    cfg = build_workflow_config(
        "target_followers", "natgeo", _base_limits(), _base_probs(),
        session_duration=60, delays={"min": 7, "max": 20},
        behavior_policy={"profileId": "careful"},
    )
    assert cfg["session_settings"]["delay_between_actions"] == {"min": 7, "max": 20}
    assert cfg["behaviorPolicy"] == {"profileId": "careful"}


def test_no_behavior_policy_leaves_config_without_top_level_key():
    cfg = build_workflow_config(
        "target_followers", "natgeo", _base_limits(), _base_probs(),
    )
    assert "behaviorPolicy" not in cfg
