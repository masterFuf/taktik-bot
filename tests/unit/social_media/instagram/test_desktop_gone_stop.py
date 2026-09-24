"""When the desktop app disappears, the Instagram session must end saying so.

The bridge's owner watchdog raises the shared halt latch with `desktop_gone`, then, if the run is
still there after its grace, sends the stop signal. Whichever of the two ends the session, the
row must carry `desktop_gone` -- not "target app crashed" (what any unknown latch code used to
become) and not "manual stop" (what the signal handler always said).
"""

import json
import signal
import time

import pytest

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.workflows.management.session import stop_reasons as sr
from taktik.core.social_media.instagram.workflows.management.session.session import SessionManager
from taktik.core.social_media.instagram.workflows.support.workflow_helpers import WorkflowHelpers


@pytest.fixture(autouse=True)
def _clean_latch():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


def test_desktop_gone_is_a_failed_stop():
    reason = sr.desktop_gone()

    assert reason.code == "desktop_gone"
    assert reason.family == sr.FAMILY_FAILED
    assert sr.terminal_status(reason) == sr.STATUS_INTERRUPTED
    # Also when it travels as the bare code (the TikTok loops pass strings).
    assert sr.terminal_status("desktop_gone") == sr.STATUS_INTERRUPTED


@pytest.mark.parametrize(
    "code, detail, expected",
    [
        (run_halt.DEVICE_DISCONNECTED, "adb gone", "device_disconnected"),
        (run_halt.TARGET_APP_CRASHED, "aerr_close", "target_app_crashed"),
        (run_halt.DESKTOP_GONE, "desktop pid 12: exited", "desktop_gone"),
    ],
)
def test_each_halt_code_has_its_motive(code, detail, expected):
    assert sr.for_halt({"code": code, "detail": detail}).code == expected


def test_the_session_limits_read_desktop_gone():
    run_halt.demander_arret(run_halt.DESKTOP_GONE, "desktop pid 12: exited")

    keep_going, reason = SessionManager({"session_settings": {}}).should_continue()

    assert keep_going is False
    assert reason.code == "desktop_gone"


class _Automation:
    def __init__(self):
        self.stats = {"start_time": time.time()}
        self.session_finalized = False
        self.current_session_id = None


def _stop_event_from_signal_handler(capsys) -> dict:
    """Register the real handler, deliver SIGINT to it, return the `session_stop` it printed."""
    previous = signal.getsignal(signal.SIGINT), signal.getsignal(signal.SIGTERM)
    helpers = WorkflowHelpers(_Automation())
    helpers._close_instagram = lambda: None  # no device in a unit test
    helpers._capture_final_screen = lambda reason: {}
    try:
        helpers.setup_signal_handlers()
        handler = signal.getsignal(signal.SIGINT)
        with pytest.raises(SystemExit):
            handler(signal.SIGINT, None)
    finally:
        signal.signal(signal.SIGINT, previous[0])
        signal.signal(signal.SIGTERM, previous[1])

    printed = [line for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    return json.loads(printed[-1])


def test_the_stop_signal_after_the_desktop_died_says_desktop_gone(capsys):
    run_halt.demander_arret(run_halt.DESKTOP_GONE, "desktop pid 12: exited")

    event = _stop_event_from_signal_handler(capsys)

    assert event["reason_code"] == "desktop_gone"
    assert event["status"] == "INTERRUPTED"


def test_a_plain_stop_signal_is_still_a_manual_stop(capsys):
    event = _stop_event_from_signal_handler(capsys)

    assert event["reason_code"] == "manual_stop"
    assert event["reason"] == "Manual stop (Ctrl+C)"
