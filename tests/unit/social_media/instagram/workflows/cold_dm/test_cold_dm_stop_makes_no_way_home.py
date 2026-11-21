"""After a stop, the cold DM makes no gesture: no way back home, no next recipient.

Kevin's rule of 2026-11-16: once the run is asked to stop (a lost network, the desktop gone, a
locked phone), the phone is left as the stop found it. The cold DM went home after every recipient,
the latch up or not, and read the latch only at the top of the next one. A stop that came while it
reached a recipient was followed by the way home, a gesture on a screen nobody reads any more.

The phone is played by doubles that write down the gestures asked of it: no screen is read here.
"""

from __future__ import annotations

import pytest

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.atomic.navigation.search_results import (
    ProfileNavigationFailure,
    ProfileNavigationFailureReason as Reason,
)
from taktik.core.social_media.instagram.workflows.cold_dm import results
from taktik.core.social_media.instagram.workflows.cold_dm import workflow as module


@pytest.fixture(autouse=True)
def no_marker(monkeypatch):
    monkeypatch.setattr(results, "record_sent_dm", lambda *args, **kwargs: None)
    monkeypatch.setattr(results, "record_pending_dm", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "wait_before_next_cold_dm", lambda **kwargs: None)


def _stop_now():
    run_halt.demander_arret(run_halt.NETWORK_LOST, "the network watch lost the phone")


def _workflow(gestures, reach):
    workflow = module.ColdDMWorkflow(object(), object())
    workflow.go_home = lambda: gestures.append("home")
    workflow.filter_pending_recipients = lambda recipients, account_id: list(recipients)
    workflow._detect_app_language = lambda: None
    workflow.reach_and_send = reach
    return workflow


def _not_found(gestures, *, stop):
    def reach(recipient, compose, policy=None, *, rules=None):
        gestures.append(f"search:{recipient}")
        if stop:
            _stop_now()
        return {"outcome": module.NOT_OPENED}
    return reach


def _sent(gestures, *, stop):
    def reach(recipient, compose, policy=None, *, rules=None):
        gestures.append(f"send:{recipient}")
        if stop:
            _stop_now()
        return {"outcome": module.SENT, "message": "Hello there", "send_result": None}
    return reach


def _raising(gestures, *, stop):
    def reach(recipient, compose, policy=None, *, rules=None):
        gestures.append(f"search:{recipient}")
        if stop:
            _stop_now()
        raise RuntimeError("the device answered nothing")
    return reach


@pytest.mark.parametrize("reach", [_not_found, _sent, _raising], ids=["not_opened", "sent", "raised"])
def test_a_stop_while_reaching_a_recipient_makes_no_way_home(reach):
    gestures = []
    workflow = _workflow(gestures, reach(gestures, stop=True))

    workflow.run(["first_handle", "second_handle"], ["Hello there"], account_id=7)

    assert gestures == ["search:first_handle" if reach is not _sent else "send:first_handle"]


@pytest.mark.parametrize("reach", [_not_found, _sent, _raising], ids=["not_opened", "sent", "raised"])
def test_without_a_stop_each_recipient_ends_at_home(reach):
    gestures = []
    workflow = _workflow(gestures, reach(gestures, stop=False))

    workflow.run(["first_handle", "second_handle"], ["Hello there"], account_id=7)

    verb = "send" if reach is _sent else "search"
    assert gestures == [f"{verb}:first_handle", "home", f"{verb}:second_handle", "home"]
