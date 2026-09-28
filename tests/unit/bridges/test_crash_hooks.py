"""The last-resort crash reporter under every bridge.

An uncaught exception used to leave nothing but a raw stderr traceback and exit 1: the desktop saw
a dead process and an exit code, never a cause. These tests pin the event it emits instead.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from bridges.common.runtime import crash_hooks

CORE = Path(__file__).resolve().parents[3]


@pytest.fixture
def captured_events(monkeypatch):
    """Capture what the hook writes to the stdout descriptor."""
    written: list[dict] = []

    def fake_write(fd, payload):
        written.append(json.loads(payload.decode("utf-8")))
        return len(payload)

    monkeypatch.setattr(crash_hooks.os, "write", fake_write)
    return written


def _raise_and_capture(exc: BaseException):
    """Raise `exc` for real so the captured triple carries a genuine traceback.

    Catches BaseException, not Exception: KeyboardInterrupt is one of the cases under test and
    would otherwise escape and abort the run.
    """
    try:
        raise exc
    except BaseException:
        return sys.exc_info()


def test_reports_type_message_and_traceback(captured_events):
    exc_type, exc_value, exc_tb = _raise_and_capture(RuntimeError("device exploded"))

    crash_hooks.report_unhandled(exc_type, exc_value, exc_tb)

    assert len(captured_events) == 1
    event = captured_events[0]
    assert event["type"] == "error"
    assert event["error_code"] == "UNHANDLED_EXCEPTION"
    assert event["error"] == "RuntimeError: device exploded"
    # The traceback is the whole point: the message alone names no frame.
    assert "RuntimeError: device exploded" in event["traceback"]
    assert "test_crash_hooks.py" in event["traceback"]


def test_traceback_is_bounded(captured_events, monkeypatch):
    monkeypatch.setattr(crash_hooks, "MAX_TRACEBACK_CHARS", 120)
    exc_type, exc_value, exc_tb = _raise_and_capture(ValueError("x" * 5000))

    crash_hooks.report_unhandled(exc_type, exc_value, exc_tb)

    assert len(captured_events[0]["traceback"]) <= 120


def test_names_the_bridge_and_thread(captured_events, monkeypatch):
    monkeypatch.setattr(crash_hooks, "_bridge_name", "desktop_bridge")
    exc_type, exc_value, exc_tb = _raise_and_capture(RuntimeError("boom"))

    crash_hooks.report_unhandled(exc_type, exc_value, exc_tb, thread="watchdog")

    event = captured_events[0]
    assert event["bridge"] == "desktop_bridge"
    assert event["thread"] == "watchdog"


def test_keyboard_interrupt_is_not_a_crash(captured_events, monkeypatch):
    # Ctrl+C is a clean stop: bridges finalize their session on it, and reporting it as a crash
    # would file every manual stop as a ticket.
    monkeypatch.setattr(crash_hooks.sys, "__excepthook__", lambda *_: None)
    exc_type, exc_value, exc_tb = _raise_and_capture(KeyboardInterrupt())

    crash_hooks._excepthook(exc_type, exc_value, exc_tb)

    assert captured_events == []


def test_ipc_failure_never_raises(monkeypatch):
    def boom(*_args, **_kwargs):
        raise OSError("pipe closed")

    monkeypatch.setattr(crash_hooks.os, "write", boom)
    exc_type, exc_value, exc_tb = _raise_and_capture(RuntimeError("boom"))

    # A closed stdout must not turn a reportable crash into a second, unreportable one.
    crash_hooks.report_unhandled(exc_type, exc_value, exc_tb)


def test_importing_the_hooks_loads_nothing_of_the_product():
    # The launcher imports the hooks before the bridge, so that an import error of the bridge is
    # reported. What importing the hooks loads on the way (the package inits on their path) fails
    # before they exist: it must not reach the engine nor the device stack.
    probe = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(CORE)!r})\n"
        "from bridges.common.runtime.crash_hooks import install_crash_hooks\n"
        "print(json.dumps(sorted(sys.modules)))\n"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    loaded = json.loads(result.stdout.strip().splitlines()[-1])

    product = [name for name in loaded if name.split(".")[0] in {"taktik", "uiautomator2", "adbutils", "requests", "PIL"}]
    assert product == []
