"""A run of hand-picked profiles that loses the phone's network ends saying so.

The run of October 2026 (C57S, Instagram 410): one profile, the phone's network cut after the door's
measure. The navigation to the profile failed, the list was over, and the session ended
`session_stop` COMPLETED / `completed`: the app filed it as a success. Three causes stacked, and
this test goes through the code of the last two with the real loop and the real end of session:

- the latch's motive only replaced a FAILED end, and a list that runs out ends `completed`;
- the status was the caller's, and the profile-list loop always said COMPLETED.

The latch is set while the navigation waits, by the network watch itself (its rule, measured twice
on the C57S's answer without network, without its thread): the line it ends on is the one the
desktop's scheduler check plays (`scheduler-run-failure.cjs`, « a run whose phone lost its network »).
"""

import json
import time
from types import SimpleNamespace

import pytest
from loguru import logger

from taktik.core.shared.device import network_probe
from taktik.core.shared.device.network_watch import NetworkWatch
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.base.base_business.profile_processing import (
    ProfileProcessingMixin,
)
from taktik.core.social_media.instagram.workflows.automation.profile_list import ProfileListWorkflowMixin
from taktik.core.social_media.instagram.workflows.common.workflow_helpers import WorkflowHelpers
from unit.ping_outputs import PING_INJOIGNABLE

#: The door's measure at the start of that run.
DEPART = {'rtt_ms': 377.3, 'packet_loss_pct': 0.0, 'received': 3, 'unreachable': False}


@pytest.fixture(autouse=True)
def _latch_lifted():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


class _Automation:
    """What the end of a session reads of the run, and no device."""

    def __init__(self):
        self.stats = {'start_time': time.time()}
        self.session_finalized = False
        self.current_session_id = None


def _end_of_session(automation: _Automation) -> WorkflowHelpers:
    helpers = WorkflowHelpers(automation)
    helpers._close_instagram = lambda: None
    helpers._capture_final_screen = lambda reason: {}
    return helpers


class _ProfileListRun(ProfileProcessingMixin, ProfileListWorkflowMixin):
    """The profile-list loop and the profile pipeline it calls, on a phone whose navigation fails."""

    def __init__(self, navigate_to_profile):
        self.logger = logger
        self.session_manager = None
        self.nav_actions = SimpleNamespace(navigate_to_profile=navigate_to_profile)
        self.stats_manager = SimpleNamespace(
            increment=lambda *args, **kwargs: None,
            display_stats=lambda *args, **kwargs: None,
            display_final_stats=lambda *args, **kwargs: None,
        )
        self.automation = SimpleNamespace(helpers=_end_of_session(_Automation()))

    def _get_session_id(self):
        return None

    def _maybe_take_break(self):
        return None


def _session_stop(capsys) -> dict:
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
    stops = [line for line in lines if line.get('type') == 'session_stop']
    assert len(stops) == 1, lines
    return stops[0]


def test_the_run_ends_on_the_lost_network_not_on_its_finished_list(capsys, monkeypatch):
    monkeypatch.setattr(network_probe, '_shell', lambda device_id, command, timeout=15: PING_INJOIGNABLE)
    watch = NetworkWatch('C57S', DEPART)

    def navigation_while_the_network_goes(username):
        assert [watch.tick(), watch.tick()] == [False, True]
        return False

    _ProfileListRun(navigation_while_the_network_goes).interact_with_profile_list(['nasa'])

    stop = _session_stop(capsys)
    assert stop['reason_code'] == 'network_lost'
    assert stop['status'] == 'INTERRUPTED'
    assert stop['reason'] == ('Network lost: no route to the Internet (ping: network is unreachable), '
                              'measured twice 3 s apart')


def test_without_a_halt_the_same_run_stays_completed(capsys):
    _ProfileListRun(lambda username: False).interact_with_profile_list(['nasa'])

    stop = _session_stop(capsys)
    assert stop['reason_code'] == 'completed'
    assert stop['status'] == 'COMPLETED'
