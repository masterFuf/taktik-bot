"""A step that crashes ends the run as a crash, with its trace, never as « sources exhausted ».

The step runner (`WorkflowRunner._dispatch_workflow_step`) caught every exception of a workflow, wrote
its text without its trace and answered « no progress ». The session loop
(`InstagramAutomation.run_workflow`) cannot tell that answer from a source gone dry: it went on with the
next step, and a pass without progress ended the session `session_stop` COMPLETED / `sources_exhausted`.
A run that died on its first step was filed as a run that had nothing left to do, for every workflow the
runner drives (targets, chosen profiles, hashtags, post links, feed, unfollow, syncs).

Under the stop latch (the phone unplugged, its network lost), the crash gives way to what the latch
saw: the run ends on the latch's motive, the crash's trace stays in the log (`settled_by_halt`).

The critical path of the same loop (an exception outside a step) asks for its trace with
`exc_info=True`, which loguru ignored: the package's logging setup now honours it
(`tests/unit/shared/diagnostics/test_log_traces.py`), and the last test proves it on that path.

The real session loop, the real runner and the real end of session run here, on no phone: the Target
driver raises on the account « nasa ».
"""

import json
import time

import pytest
from loguru import logger

import taktik.core.social_media.instagram.workflows.automation.automation as automation_module
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.workflows.automation.automation import InstagramAutomation
from taktik.core.social_media.instagram.workflows.automation.workflow_runner import WorkflowRunner
from taktik.core.social_media.instagram.workflows.common.workflow_helpers import WorkflowHelpers


class DeviceGone(RuntimeError):
    """The failure the Target workflow meets on the account « nasa »."""


class SessionBroke(RuntimeError):
    """A failure outside any step: the session's own check."""


class _Session:
    """A session that always allows more: only the steps decide how the run ends."""

    def should_continue(self):
        return True, None

    def get_delay_between_actions(self):
        return 0


class _BrokenSession(_Session):
    def should_continue(self):
        raise SessionBroke('session broke')


class _Run(InstagramAutomation):
    """The real session loop and the real end of session, on an object built only from what they touch."""

    def __init__(self, steps):
        self.logger = logger
        self.config = {'actions': steps}
        self.session_manager = _Session()
        self.session_finalized = False
        self.active_account_id = 1
        self.current_session_id = None
        self.stats = {'start_time': time.time()}
        self.workflow_runner = WorkflowRunner(self)
        self.helpers = WorkflowHelpers(self)
        self.helpers.initialize_session = lambda: 1
        self.helpers._close_instagram = lambda: None
        self.helpers._capture_final_screen = lambda reason: {}
        self.targets_opened = []

    def update_session_manager_config(self):
        pass

    def _install_health_witness(self):
        pass

    def interact_with_followers(self, target_usernames=None, **kwargs):
        self.targets_opened.extend(target_usernames)
        if target_usernames == ['nasa']:
            raise DeviceGone('device gone')
        return {'processed': 0}


def _target(username):
    return {'type': 'interact_with_followers', 'target_username': username, 'max_interactions': 5}


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    monkeypatch.setattr(automation_module.time, 'sleep', lambda *args, **kwargs: None)


@pytest.fixture
def records():
    """What the run writes to its log, from WARNING up."""
    kept = []
    sink = logger.add(lambda message: kept.append(message.record), level='WARNING')
    yield kept
    logger.remove(sink)


def _session_stops(capsys) -> list:
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
    return [line for line in lines if line.get('type') == 'session_stop']


def test_a_crashed_step_ends_the_run_on_the_crash_not_as_sources_exhausted(capsys):
    _Run([_target('nasa')]).run_workflow()

    stops = _session_stops(capsys)
    assert len(stops) == 1, stops
    assert stops[0]['reason_code'] == 'crashed'
    assert stops[0]['status'] == 'INTERRUPTED'
    assert stops[0]['reason'] == 'Workflow crashed: device gone'


def test_a_crashed_step_under_the_stop_latch_ends_on_the_latch(capsys, records):
    """The phone was unplugged during the step: the guard raised the latch, then the step's next
    call to the phone raised. The run ends on what the latch saw, not as a crash; the crash's trace
    stays in the log."""
    run = _Run([_target('nasa')])
    reach_the_phone = run.interact_with_followers

    def unplugged(target_usernames=None, **kwargs):
        run_halt.demander_arret(run_halt.DEVICE_DISCONNECTED, 'usb gone')
        return reach_the_phone(target_usernames=target_usernames, **kwargs)

    run.interact_with_followers = unplugged
    run.run_workflow()

    stops = _session_stops(capsys)
    assert len(stops) == 1, stops
    assert stops[0]['reason_code'] == 'device_disconnected'
    assert stops[0]['status'] == 'INTERRUPTED'
    assert any(record['exception'] is not None and record['exception'].type is DeviceGone
               for record in records), "the crash's trace is gone"


def test_the_run_does_not_go_on_after_a_crashed_step():
    run = _Run([_target('nasa'), _target('esa')])

    run.run_workflow()

    assert run.targets_opened == ['nasa'], "the run went on after its step crashed"


def test_a_crashed_step_is_logged_with_its_trace(records):
    _Run([_target('nasa')]).run_workflow()

    traced = [record for record in records if record['exception'] is not None]
    assert traced, [record['message'] for record in records]
    assert traced[0]['exception'].type is DeviceGone


def test_a_step_without_progress_still_ends_as_sources_exhausted(capsys):
    """The guard: a step that ran and found nothing is not a crash."""
    _Run([_target('esa')]).run_workflow()

    stops = _session_stops(capsys)
    assert len(stops) == 1, stops
    assert stops[0]['reason_code'] == 'sources_exhausted'
    assert stops[0]['status'] == 'COMPLETED'


def test_a_crash_outside_a_step_ends_like_a_crashed_step(capsys):
    """One crash status for the whole loop: the critical path filed ERROR where a crashed step (and
    the chosen-profiles loop) file INTERRUPTED, the status of a failed run."""
    run = _Run([_target('esa')])
    run.session_manager = _BrokenSession()

    run.run_workflow()

    stops = _session_stops(capsys)
    assert len(stops) == 1, stops
    assert stops[0]['reason_code'] == 'crashed'
    assert stops[0]['status'] == 'INTERRUPTED'


def test_a_crash_outside_a_step_is_logged_with_its_trace(records):
    run = _Run([_target('esa')])
    run.session_manager = _BrokenSession()

    run.run_workflow()

    traced = [record for record in records if record['exception'] is not None]
    assert traced, [record['message'] for record in records]
    assert traced[0]['exception'].type is SessionBroke
