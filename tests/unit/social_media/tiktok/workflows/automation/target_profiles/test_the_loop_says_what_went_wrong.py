"""The loop of hand-picked TikTok profiles says what went wrong.

A crash in the loop is not the end of the list: the session ends on the failure code TikTok's
catalogue names (`error`), with the trace in the log, never on `unknown` with the text alone. A home
screen the loop cannot reach again is said as a warning, not hidden at debug level. Instagram's
direct loop got the same fix (`.../instagram/.../profile_list/test_the_loop_says_what_went_wrong.py`).
"""

import logging

from taktik.core.social_media.tiktok.workflows.automation.followers.models import FollowersStats
from taktik.core.social_media.tiktok.workflows.automation.target_profiles import workflow as target_module
from taktik.core.social_media.tiktok.workflows.automation.target_profiles import (
    TargetProfilesConfig,
    TargetProfilesWorkflow,
)

LOGGER_NAME = "test.tiktok.target_profiles"


class _SessionRepo:
    """Records how the session was ended."""

    def __init__(self):
        self.ended = []

    def end_session(self, **kwargs):
        self.ended.append(kwargs)


def _workflow(repo):
    workflow = TargetProfilesWorkflow.__new__(TargetProfilesWorkflow)
    workflow.config = TargetProfilesConfig(usernames=["user_1"])
    workflow.logger = logging.getLogger(LOGGER_NAME)
    workflow._followers_repository = repo
    workflow._account_id = 1
    workflow._session_id = 2
    workflow._processed_usernames = set()
    workflow._paused = False
    workflow._check_limits_reached = lambda: None
    return workflow


def test_a_crash_in_the_loop_ends_the_session_as_a_failure_with_its_trace(caplog):
    repo = _SessionRepo()
    workflow = _workflow(repo)

    def _crash():
        raise RuntimeError("screen gone")

    workflow._handle_popups = _crash

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        stats = workflow.run(bot_username=None)

    assert isinstance(stats, FollowersStats)
    assert repo.ended[-1]["status"] == "ERROR"
    assert repo.ended[-1]["stats"]["completion_reason"] == "error"
    assert stats.completion_reason == "error"
    crash_lines = [r for r in caplog.records if "crashed" in r.getMessage()]
    assert crash_lines, "the crash is not logged"
    assert crash_lines[0].levelno == logging.ERROR
    assert crash_lines[0].exc_info is not None, "the crash is logged without its trace"


def test_a_home_screen_not_reached_again_is_a_warning(monkeypatch, caplog):
    workflow = _workflow(_SessionRepo())
    workflow.device = object()

    def _fails(*_args, **_kwargs):
        raise RuntimeError("no home tab")

    monkeypatch.setattr(target_module, "return_to_tiktok_home", _fails)

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        workflow._recover_to_home()

    lines = [r for r in caplog.records if "home" in r.getMessage().lower()]
    assert lines and lines[0].levelno == logging.WARNING
    assert "no home tab" in lines[0].getMessage()
