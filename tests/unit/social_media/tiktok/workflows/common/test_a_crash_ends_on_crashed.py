"""A TikTok loop that crashes ends on `crashed`, with its trace, like an Instagram run.

Each loop caught every exception at its head, logged the text without the trace and left the run
without a motive (`unknown`, or nothing at all for the video feeds). They now share one end of a
crash (`BaseTikTokWorkflow._crash_reason`): the full trace in the log, then `crashed`, the motive
Instagram's crash path names. A run the stop latch had already stopped (phone unplugged, network
lost) keeps the latch's motive: the call that raised is the latch's cause seen from afar, as on
Instagram (`settled_by_halt`).
"""

import logging
from types import SimpleNamespace

import pytest

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.tiktok.workflows.automation.followers.workflow import FollowersWorkflow
from taktik.core.social_media.tiktok.workflows.automation.for_you.workflow import ForYouWorkflow
from taktik.core.social_media.tiktok.workflows.automation.search.workflow import SearchWorkflow
from taktik.core.social_media.tiktok.workflows.automation.sync_lists.workflow import SyncListsWorkflow
from taktik.core.social_media.tiktok.workflows.common.models import VideoWorkflowStats

LOGGER_NAME = "test.tiktok.crash"


@pytest.fixture(autouse=True)
def _clean_latch():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


def _crash(*_args, **_kwargs):
    raise RuntimeError("screen gone")


class _SessionRepo:
    def __init__(self):
        self.ended = []

    def end_session(self, **kwargs):
        self.ended.append(kwargs)


def _followers_workflow():
    workflow = FollowersWorkflow.__new__(FollowersWorkflow)
    workflow.config = SimpleNamespace(
        search_query="target_1", max_followers=5, min_posts_per_profile=1, max_posts_per_profile=2,
        max_consecutive_known_usernames=0,
    )
    workflow.logger = logging.getLogger(LOGGER_NAME)
    workflow._followers_repository = _SessionRepo()
    workflow._account_id = 1
    workflow._session_id = 2
    workflow._processed_usernames = set()
    workflow._navigate_to_followers_list = _crash
    return workflow


def _video_workflow(cls):
    workflow = cls.__new__(cls)
    workflow.config = SimpleNamespace(
        search_query="query_1", max_videos=5, like_probability=0.0, follow_probability=0.0,
    )
    workflow.logger = logging.getLogger(LOGGER_NAME)
    workflow.stats = VideoWorkflowStats()
    workflow._ensure_on_for_you = _crash
    workflow._navigate_to_search_videos = _crash
    return workflow


def _sync_workflow():
    workflow = SyncListsWorkflow.__new__(SyncListsWorkflow)
    workflow.logger = logging.getLogger(LOGGER_NAME)
    workflow._resolve_account = lambda _username: True
    workflow._lists_to_sync = lambda: ["following"]
    workflow._sync_one_list = _crash
    return workflow


def _assert_crash_logged_with_trace(caplog):
    lines = [r for r in caplog.records if "crashed" in r.getMessage()]
    assert lines, "the crash is not logged"
    assert lines[0].levelno == logging.ERROR
    assert lines[0].exc_info is not None, "the crash is logged without its trace"


def test_the_followers_loop_ends_a_crash_on_crashed(caplog):
    workflow = _followers_workflow()

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        stats = workflow.run(bot_username=None)

    ended = workflow._followers_repository.ended[-1]
    assert ended["status"] == "ERROR"
    assert ended["stats"]["completion_reason"] == "crashed"
    assert stats.completion_reason == "crashed"
    _assert_crash_logged_with_trace(caplog)


@pytest.mark.parametrize("cls", [ForYouWorkflow, SearchWorkflow])
def test_a_video_feed_ends_a_crash_on_crashed(cls, caplog):
    workflow = _video_workflow(cls)

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        stats = workflow.run()

    assert stats.completion_reason == "crashed"
    _assert_crash_logged_with_trace(caplog)


def test_the_list_sync_ends_a_crash_on_crashed(caplog):
    workflow = _sync_workflow()

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        stats = workflow.run(bot_username="account_1")

    assert stats.completion_reason == "crashed"
    _assert_crash_logged_with_trace(caplog)


def test_under_the_stop_latch_a_crash_ends_on_the_latch_motive(caplog):
    run_halt.demander_arret(run_halt.DEVICE_DISCONNECTED, "adb link lost")
    workflow = _followers_workflow()

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        stats = workflow.run(bot_username=None)

    assert stats.completion_reason == "device_disconnected"
    assert workflow._followers_repository.ended[-1]["stats"]["completion_reason"] == "device_disconnected"
    _assert_crash_logged_with_trace(caplog)
