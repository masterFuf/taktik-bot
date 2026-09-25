"""Two defects of the Cartography Lab session found on the phones on 2026-09-23 (C0, C2).

1. The TikTok `app.launch` relaunched TikTok on ANOTHER phone. It built a `TikTokManager()`
   without a serial, and `restart()` called `connect()` with none, which takes the first phone of
   `adb devices`: the session drove the 6a, TikTok was stopped there and started on the 4a.
2. The language was detected when the session opened, before `app.launch`, with the app closed:
   the launcher's dump holds none of the app's words, the answer was `unknown`, and the session
   never asked again. Every result said `applied: false` on the four phones.
"""

import io
import json
import types

import pytest

import taktik.core.shared.device.manager as device_manager_module
from bridges.compat.diagnostics.actions.tiktok import ACTION_REGISTRY, register_actions
from bridges.compat.diagnostics.runtime.action_test import runner, session
from bridges.compat.diagnostics.runtime.action_test.action_bundle import ActionBundle, attach_device_id
from bridges.compat.diagnostics.runtime.action_test.language import LabLanguage

TIKTOK = "com.zhiliaoapp.musically"


class _Phone:
    """One connected phone: records what was started and stopped on it."""

    def __init__(self, serial, foreground="com.google.android.apps.nexuslauncher"):
        self.serial = serial
        self.foreground = foreground
        self.started = []
        self.stopped = []

    def app_info(self, package):
        return {"packageName": package} if package == TIKTOK else None

    def app_stop(self, package):
        self.stopped.append(package)
        if self.foreground == package:
            self.foreground = "com.google.android.apps.nexuslauncher"

    def app_start(self, package, activity=None, stop=False):
        self.started.append(package)
        self.foreground = package

    def app_current(self):
        return {"package": self.foreground, "activity": ".Main"}

    def xpath(self, selector):
        return types.SimpleNamespace(exists=False, all=lambda: [])


class _Facade:
    """What the bundle holds: a facade over the raw device, as the TikTok one is."""

    def __init__(self, raw):
        self._device = raw

    def __getattr__(self, name):
        return getattr(self._device, name)


@pytest.fixture(autouse=True)
def no_adb(monkeypatch):
    """No test here may reach a real phone: the old code's fallbacks call adb without a serial."""

    def _refuse(*args, **kwargs):
        raise AssertionError(f"adb must not run in a unit test: {args!r}")

    monkeypatch.setattr(device_manager_module.subprocess, "run", _refuse)
    monkeypatch.setattr(device_manager_module.DeviceManager, "_apply_selector_overrides",
                        staticmethod(lambda device_id: None))


@pytest.fixture
def no_sleep(monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda seconds: None)


@pytest.fixture
def adb_lists_another_phone_first(monkeypatch):
    """`adb devices` lists the 4a first; connecting to it is recorded, and must not happen."""
    other = _Phone("4A-SERIAL")
    connected = []
    monkeypatch.setattr(
        device_manager_module.DeviceManager, "list_devices", classmethod(lambda cls: [{"id": "4A-SERIAL"}])
    )

    def _connect(serial):
        connected.append(serial)
        return other

    monkeypatch.setattr(device_manager_module.u2, "connect", _connect)
    return types.SimpleNamespace(other=other, connected=connected)


def test_app_launch_restarts_tiktok_on_the_session_phone(no_sleep, adb_lists_another_phone_first):
    register_actions()
    phone = _Phone("6A-SERIAL")
    bundle = ActionBundle()
    bundle.device = _Facade(phone)
    attach_device_id(bundle, "6A-SERIAL")

    result = ACTION_REGISTRY["app.launch"](bundle, {})

    assert result is True
    assert phone.stopped == [TIKTOK] and phone.started == [TIKTOK]
    # Nothing was connected, and the other phone was never touched.
    assert adb_lists_another_phone_first.connected == []
    assert adb_lists_another_phone_first.other.started == []


def test_app_launch_takes_the_serial_from_the_connected_device(no_sleep, adb_lists_another_phone_first):
    """A bundle built before the serial was recorded still knows its phone: the device's own."""
    register_actions()
    phone = _Phone("6A-SERIAL")
    bundle = ActionBundle()
    bundle.device = _Facade(phone)

    assert ACTION_REGISTRY["app.launch"](bundle, {}) is True
    assert adb_lists_another_phone_first.connected == []


def test_app_launch_refuses_when_the_phone_is_unknown(no_sleep, adb_lists_another_phone_first):
    register_actions()
    bundle = ActionBundle()
    bundle.device = types.SimpleNamespace(app_current=lambda: {"package": "x"})

    result = ACTION_REGISTRY["app.launch"](bundle, {})

    assert result["success"] is False
    assert adb_lists_another_phone_first.connected == []


# ── Language ─────────────────────────────────────────────────────────────────


def _detector(phone, calls):
    """The real detector's behaviour: the app's words are only on screen with the app in front."""

    def _detect(platform, device, override=None):
        calls.append(phone.foreground)
        known = override or (phone.foreground == TIKTOK)
        language = (override or "fr") if known else "unknown"
        return {"platform": platform, "language": language, "applied": bool(known),
                "reason": None if known else "language_unknown", "timingMs": 1.0}

    return _detect


def test_the_language_is_not_read_off_the_launcher():
    phone = _Phone("6A-SERIAL")
    calls = []
    language = LabLanguage("tiktok", _Facade(phone), _detector(phone, calls))

    payload = language.refresh()

    assert payload["applied"] is False
    assert payload["reason"] == "app_not_in_foreground"
    assert calls == []  # no dump taken with the launcher on screen


def test_the_language_is_detected_once_the_app_is_in_front_and_only_once():
    phone = _Phone("6A-SERIAL")
    calls = []
    language = LabLanguage("tiktok", _Facade(phone), _detector(phone, calls))
    language.refresh()

    phone.foreground = TIKTOK
    assert language.refresh()["language"] == "fr"
    assert language.refresh()["language"] == "fr"
    assert calls == [TIKTOK]


def test_a_forced_language_needs_no_screen():
    phone = _Phone("6A-SERIAL")
    calls = []
    language = LabLanguage("tiktok", _Facade(phone), _detector(phone, calls), override="en")

    assert language.refresh()["language"] == "en"
    assert len(calls) == 1


def test_the_session_reports_the_language_from_the_app_launch_result_on(monkeypatch):
    """The session opens app closed; `app.launch` brings TikTok up; its OWN result has the language."""
    phone = _Phone("6A-SERIAL")
    calls = []

    class _DeviceManager:
        def __init__(self, device_id):
            self.device = phone

        def connect(self, verify_atx=False):
            return True

    def _launch(bundle, params):
        phone.app_start(TIKTOK)
        return True

    emitted = []
    monkeypatch.setattr(device_manager_module, "DeviceManager", _DeviceManager)
    monkeypatch.setattr(session, "_load_config", lambda: {"device_id": "6A-SERIAL", "platform": "tiktok",
                                                           "capture_artifacts": False})
    monkeypatch.setattr(session, "_load_platform_runtime", lambda platform: (
        {"app.launch": _launch, "tt.detection.is_for_you": lambda b, p: True},
        _Facade,
        lambda facade: types.SimpleNamespace(device=facade),
    ))
    monkeypatch.setattr(session, "_detect_and_optimize_selectors", _detector(phone, calls))
    monkeypatch.setattr(session, "emit", emitted.append)
    monkeypatch.setattr(runner, "emit", emitted.append)
    commands = [
        {"type": "run_action", "action_id": "app.launch", "request_id": "1"},
        {"type": "run_action", "action_id": "tt.detection.is_for_you", "request_id": "2"},
        {"type": "close"},
    ]
    monkeypatch.setattr(session.sys, "stdin", io.StringIO("".join(json.dumps(c) + "\n" for c in commands)))

    session.run_action_session_bridge()

    ready = next(e for e in emitted if e["type"] == "session_ready")
    results = {e["request_id"]: e for e in emitted if e["type"] == "result"}
    assert ready["language_optimization"]["applied"] is False
    assert results["1"]["language_optimization"]["language"] == "fr"
    assert results["2"]["language_optimization"]["language"] == "fr"
    assert calls == [TIKTOK]
