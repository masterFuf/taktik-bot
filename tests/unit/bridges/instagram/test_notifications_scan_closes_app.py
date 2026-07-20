"""The notifications scan owns Instagram's lifecycle: it opens it, and it closes it.

Operator report: after a manual Notifications run, Instagram stayed open on the activity
screen. The scan force-restarts the app to reach a known state, so it must also put the phone
back to a clean state when it is done — the same contract every other workflow already honours
through its bridge teardown.

Per-row actions (accept / ignore / reply / like) deliberately do NOT close it: they are
interactive follow-ups on the screen the operator is looking at, and they self-heal through the
workflow's relauncher when Instagram has drifted or been closed since the scan.
"""

import sys
import types

import pytest

import bridges.instagram.engagement.runtime.notifications.commands as commands


class _Bridge:
    def __init__(self):
        self.restarted = 0
        self.stopped = 0
        self.workflow = _Workflow()

    def connect(self):
        return True

    def restart_instagram(self):
        self.restarted += 1

    def stop(self):
        self.stopped += 1
        return True

    def build_workflow(self):
        return self.workflow


class _Workflow:
    def scan(self, **_kwargs):
        return {"success": True, "count": 0, "by_type": {}, "items": [], "requests": []}

    def list_requests(self, **_kwargs):
        return {"success": True, "count": 0, "requests": []}

    def accept_request(self, _username):
        return {"success": True}


@pytest.fixture
def bridge(monkeypatch):
    created = _Bridge()
    monkeypatch.setattr(commands, "NotificationsBridge", lambda *a, **k: created)
    # Keep the test silent and free of persistence side effects.
    monkeypatch.setattr(commands, "emit_notif_json", lambda *a, **k: None)
    monkeypatch.setattr(commands, "emit_notif_step", lambda *a, **k: None)
    monkeypatch.setattr(commands, "build_known_checker", lambda *a, **k: None)
    monkeypatch.setattr(commands, "record_scan_notifications", lambda *a, **k: [])
    return created


def test_scan_restarts_then_closes_instagram(bridge):
    commands.cmd_scan("device-1", 3)

    assert bridge.restarted == 1  # opened to a known state
    assert bridge.stopped == 1    # and closed once the feed was read


def test_per_row_action_leaves_instagram_open(bridge):
    # The operator is working through the scanned rows; closing the app between two taps
    # would force a full restart for every single accept.
    commands.cmd_accept("device-1", "someone")

    assert bridge.restarted == 0
    assert bridge.stopped == 0


def test_list_requests_leaves_instagram_open(bridge):
    commands.cmd_list_requests("device-1", 50)

    assert bridge.stopped == 0
