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
