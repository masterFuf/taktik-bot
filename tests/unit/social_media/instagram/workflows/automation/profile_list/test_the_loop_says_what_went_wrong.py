"""The loop of hand-picked profiles says what went wrong, and a crash ends the run as a crash.

A crash: the loop caught every exception, wrote its text without its trace and gave back its counters
with an empty motive. The driver (`InstagramAutomation.interact_with_profiles`) read that as a list gone
through: the session ended `session_stop` COMPLETED / `completed`, the app filed the run as a success,
and the trace that would have said where it broke was lost.

A check that cannot answer: before each visit the loop asks the database whether the account already
handled the profile. When the database did not answer, the loop visited the profile anyway (that stays)
and said so only at debug level, below what a run log keeps.

The real loop, the real driver and the real end of session run here, on no phone: the profile
pipeline answers each profile « visited, no gesture drawn ».
"""

import json
import sqlite3
import time
from types import SimpleNamespace

import pytest
from loguru import logger

from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.base.base_business.profile_processing import (
    ProfileProcessingResult,
)
from taktik.core.social_media.instagram.workflows.automation.automation import InstagramAutomation
from taktik.core.social_media.instagram.workflows.automation.profile_list import ProfileListWorkflowMixin
from taktik.core.social_media.instagram.workflows.common.workflow_helpers import WorkflowHelpers


class StatsDisplayBroke(RuntimeError):
    """The failure the loop meets after its first profile."""


@pytest.fixture(autouse=True)
def _latch_lifted():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


@pytest.fixture(autouse=True)
def _no_profile_known(monkeypatch):
    """The « already handled » check answers « unknown » without a database."""
    monkeypatch.setattr(InstagramWorkflowStateService, 'is_profile_skippable',
                        staticmethod(lambda *args, **kwargs: (False, None)))


@pytest.fixture
def records():
    """What the run writes to its log, from WARNING up."""
    kept = []
    sink = logger.add(lambda message: kept.append(message.record), level='WARNING')
    yield kept
    logger.remove(sink)


def _broken_display(*args, **kwargs):
    raise StatsDisplayBroke('stats display broke')


class _ProfileListLoop(ProfileListWorkflowMixin):
    """The profile-list loop, on a pipeline that visits each profile without a gesture."""

    def __init__(self, display_stats=lambda *args, **kwargs: None):
        self.logger = logger
        self.session_manager = None
        self.automation = None
        self.visited = []
        self.stats_manager = SimpleNamespace(
            increment=lambda *args, **kwargs: None,
            display_stats=display_stats,
            display_final_stats=lambda *args, **kwargs: None,
        )

    def _process_profile_on_screen(self, username, config, **kwargs):
        self.visited.append(username)
        return ProfileProcessingResult(ProfileProcessingResult.SKIPPED_PROBABILITY, username)

    def _get_session_id(self):
        return None

    def _maybe_take_break(self):
        return None


class _Driver(InstagramAutomation):
    """The real driver method and the real end of session, on an object built only from what they touch."""

    def __init__(self, loop):
        self.logger = logger
        self.active_account_id = 1
        self.session_finalized = False
        self.current_session_id = None
        self.stats = {'start_time': time.time()}
        self.actions = SimpleNamespace(follower_business=loop)
        self.helpers = WorkflowHelpers(self)
        self.helpers._close_instagram = lambda: None
        self.helpers._capture_final_screen = lambda reason: {}


def _session_stop(capsys) -> dict:
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
    stops = [line for line in lines if line.get('type') == 'session_stop']
    assert len(stops) == 1, lines
    return stops[0]


def test_a_crash_ends_the_run_on_the_crash_not_as_a_success(capsys):
    loop = _ProfileListLoop(display_stats=_broken_display)

    _Driver(loop).interact_with_profiles(target_usernames=['nasa', 'esa'], max_interactions=5, config={})

    assert loop.visited == ['nasa'], "the loop went on after it broke"
    stop = _session_stop(capsys)
    assert stop['reason_code'] == 'crashed'
    assert stop['status'] == 'INTERRUPTED'
    assert stop['reason'] == 'Workflow crashed: stats display broke'


def test_a_crash_is_logged_with_its_trace(records):
    _Driver(_ProfileListLoop(display_stats=_broken_display)).interact_with_profiles(
        target_usernames=['nasa'], max_interactions=5, config={})

    traced = [record for record in records if record['exception'] is not None]
    assert traced, [record['message'] for record in records]
    assert traced[0]['exception'].type is StatsDisplayBroke


def test_a_skip_check_without_an_answer_is_said_and_the_profile_still_visited(monkeypatch, capsys, records):
    def database_locked(*args, **kwargs):
        raise sqlite3.OperationalError('database is locked')

    monkeypatch.setattr(InstagramWorkflowStateService, 'is_profile_skippable', staticmethod(database_locked))
    loop = _ProfileListLoop()

    _Driver(loop).interact_with_profiles(target_usernames=['nasa'], max_interactions=5, config={})

    assert loop.visited == ['nasa'], "a check without an answer must not skip the profile"
    said = [record['message'] for record in records if record['level'].name == 'WARNING']
    assert any('@nasa' in message and 'database is locked' in message for message in said), said
    assert _session_stop(capsys)['reason_code'] == 'completed'
