"""The Post URL options must survive TWO whitelists to reach the run.

Both config builders name their keys explicitly, so a key neither of them lists is dropped
in silence: the operator ticks a box, the run ignores it, and nothing says so. These tests
walk the real chain — desktop JSON -> action dict -> workflow config — rather than trusting
either half on its own.
"""

import pytest

from taktik.core.social_media.instagram.workflows.core.config_builder import (
    build_instagram_automation_config,
)
from taktik.core.social_media.instagram.workflows.management.config.config import (
    WorkflowConfigBuilder,
)

IN_THREAD_KEYS = (
    "source_mode", "like_comments", "reply_to_comments",
    "max_comment_likes", "max_comment_replies", "walk_profiles",
)


def _desktop_payload(**extra):
    return {
        "deviceId": "dev", "workflowType": "post_url",
        "target": "https://instagram.com/p/ABC",
        "limits": {"maxProfiles": 20, "maxLikesPerProfile": 2},
        "probabilities": {"like": 70, "follow": 20, "comment": 10,
                          "watchStories": 0, "likeStories": 0},
        "filters": {"minFollowers": 100, "maxFollowers": 50000,
                    "minPosts": 3, "maxFollowing": 7500},
        "session": {"durationMinutes": 60},
        **extra,
    }


def _run_config(**extra):
    action = build_instagram_automation_config(_desktop_payload(**extra))["actions"][0]
    return WorkflowConfigBuilder.build_post_url_config(action)


def test_every_in_thread_option_reaches_the_workflow():
    config = _run_config(
        source_mode="commenters", like_comments=True, reply_to_comments=True,
        max_comment_likes=5, max_comment_replies=2, walk_profiles=False,
    )
    assert {key: config.get(key) for key in IN_THREAD_KEYS} == {
        "source_mode": "commenters", "like_comments": True, "reply_to_comments": True,
        "max_comment_likes": 5, "max_comment_replies": 2, "walk_profiles": False,
    }


def test_a_run_that_specifies_nothing_is_left_exactly_as_before():
    """Existing runs and already-scheduled jobs must not change behaviour."""
    config = _run_config()
    assert [key for key in IN_THREAD_KEYS if key in config] == []


def test_switching_the_modes_off_reaches_the_workflow_as_off():
    """False must travel — dropping it would silently re-enable whatever the default is."""
    config = _run_config(like_comments=False, reply_to_comments=False, walk_profiles=True)
    assert config["like_comments"] is False
    assert config["reply_to_comments"] is False
    assert config["walk_profiles"] is True


@pytest.mark.parametrize("sent,expected", [
    ("commenters", "commenters"), ("Commenters", "commenters"),
    ("likers", "likers"), ("typo", "likers"),
])
def test_the_source_mode_is_normalised_and_unknown_values_fall_back(sent, expected):
    assert _run_config(source_mode=sent)["source_mode"] == expected
