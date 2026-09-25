"""A keyboard switch returns only once Android has bound the ADB keyboard.

Before: `ime set` answered, the text broadcast left at once and reached no receiver. The first text
of every session was lost (a Pixel 4a hashtag search stayed empty).
"""

import pytest

from taktik.core.shared.input import taktik_keyboard as kb

ADB = kb.TAKTIK_KEYBOARD_IME


def _dumpsys(cur, connected):
    flag = "true" if connected else "false"
    return (f"  mCurMethodId={cur}\n"
            f"  mCurId={cur} mHaveConnection={flag} mBoundToMethod={flag} mVisibleBound=false\n")


class Phone:
    """Switches to the ADB keyboard at `ime set`, and binds it `bind_after` dumpsys reads later."""

    def __init__(self, bind_after):
        self.default = kb.GBOARD_IME
        self.bind_after = bind_after
        self.reads = 0
        self.log = []

    def __call__(self, device_id, command):
        self.log.append(command)
        if command == "settings get secure default_input_method":
            return self.default
        if command.startswith("ime set "):
            self.default = command[len("ime set "):]
            return f"Input method {self.default} selected for user #0"
        if command == "dumpsys input_method":
            self.reads += 1
            if self.default != ADB:
                return _dumpsys(kb.GBOARD_IME, True)
            return _dumpsys(ADB, self.reads > self.bind_after)
        return ""


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(kb, "_original_ime", {})
    monkeypatch.setattr(kb, "_active_ime_cache", {})
    monkeypatch.setattr(kb, "_atexit_registered", True)
    monkeypatch.setattr(kb, "_BIND_POLL_SECONDS", 0, raising=False)
    monkeypatch.setattr(kb.time, "sleep", lambda s: None)


def test_activation_waits_until_the_keyboard_is_bound(monkeypatch):
    phone = Phone(bind_after=3)
    monkeypatch.setattr(kb, "run_adb_shell", phone)

    assert kb.activate_taktik_keyboard("4a") is True
    # Returned only after the read that showed the ADB keyboard bound with a connection.
    assert phone.reads == 4
    assert phone.log[-1] == "dumpsys input_method"


def test_an_unreadable_dumpsys_does_not_hold_the_switch(monkeypatch):
    calls = []

    def adb(device_id, command):
        calls.append(command)
        if command.startswith("ime set "):
            return "Input method selected"
        return ""

    monkeypatch.setattr(kb, "run_adb_shell", adb)
    assert kb.activate_taktik_keyboard("old") is True
    assert calls.count("dumpsys input_method") == 1


def test_a_keyboard_never_bound_gives_up_after_the_timeout(monkeypatch):
    phone = Phone(bind_after=10 ** 9)
    monkeypatch.setattr(kb, "run_adb_shell", phone)
    clock = iter(range(0, 100))
    monkeypatch.setattr(kb.time, "time", lambda: next(clock))

    assert kb.activate_taktik_keyboard("slow") is True
    assert phone.reads <= kb._BIND_TIMEOUT_SECONDS + 2
