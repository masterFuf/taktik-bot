"""A cap of 0 turns its gesture off; it never ends the TikTok run.

"0 like" is a pure watch-time run (Kevin, 2026-09-24). The session check read `0 >= 0` as "likes
budget spent" and ended a For You run before its first video (orphan test on the Pixel 6a).
"""

import types

import pytest

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.tiktok.actions.business.workflows._internal.base_video_workflow import (
    BaseVideoWorkflow,
)
from taktik.core.social_media.tiktok.actions.business.workflows.followers.workflow import FollowersWorkflow


class _Log:
    def info(self, *a, **k):
        pass

    warning = debug = info


@pytest.fixture(autouse=True)
def _no_halt():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


def _video_run(likes_cap, follows_cap, liked=0, followed=0):
    return types.SimpleNamespace(
        logger=_Log(),
        config=types.SimpleNamespace(max_likes_per_session=likes_cap, max_follows_per_session=follows_cap),
        stats=types.SimpleNamespace(videos_liked=liked, users_followed=followed),
    )


def _followers_run(likes_cap, follows_cap, liked=0, followed=0):
    return types.SimpleNamespace(
        logger=_Log(),
        config=types.SimpleNamespace(max_likes_per_session=likes_cap, max_follows_per_session=follows_cap),
        stats=types.SimpleNamespace(likes=liked, follows=followed),
    )


def test_zero_caps_do_not_end_a_video_run():
    assert BaseVideoWorkflow._check_limits_reached(_video_run(0, 0)) is False


def test_a_spent_non_zero_cap_still_ends_a_video_run():
    assert BaseVideoWorkflow._check_limits_reached(_video_run(3, 0, liked=3)) is True
    assert BaseVideoWorkflow._check_limits_reached(_video_run(0, 2, followed=2)) is True


def test_zero_caps_do_not_end_a_followers_run():
    assert FollowersWorkflow._check_limits_reached(_followers_run(0, 0)) == ''


def test_a_spent_non_zero_cap_still_ends_a_followers_run():
    assert FollowersWorkflow._check_limits_reached(_followers_run(3, 0, liked=3)) == 'max_likes_reached'
    assert FollowersWorkflow._check_limits_reached(_followers_run(0, 2, followed=2)) == 'max_follows_reached'
