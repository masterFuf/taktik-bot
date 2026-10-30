"""The lock of the phone's screen (`taktik/core/shared/device/screen.py`).

A scraping on a C57S (Android 14, 2026-10-30) ran a minute on the lock screen and ended
`target_never_reached`: nothing in the engine read the lock. The outputs below are lines of real
`dumpsys window` dumps: the C57S writes each state on a line of its own, a Nokia on Android 11 both on one.
"""
import subprocess

import pytest

from taktik.core.shared.device import screen

ANDROID_14_LOCKED = (
    "WINDOW MANAGER POLICY STATE (dumpsys window policy)\n"
    "    mDreamingLockscreen=true\n"
    "    isKeyguardShowing=true\n"
)
ANDROID_14_UNLOCKED = (
    "WINDOW MANAGER POLICY STATE (dumpsys window policy)\n"
    "    mDreamingLockscreen=false\n"
    "    isKeyguardShowing=false\n"
)
ANDROID_11_LOCKED = "    mDreamingLockscreen=true mDreamingSleepToken=null isKeyguardShowing=true\n"
ANDROID_11_UNLOCKED = "    mDreamingLockscreen=false mDreamingSleepToken=null isKeyguardShowing=false\n"


@pytest.mark.parametrize("output, showing", [
    (ANDROID_14_LOCKED, True),
    (ANDROID_14_UNLOCKED, False),
    (ANDROID_11_LOCKED, True),
    (ANDROID_11_UNLOCKED, False),
])
def test_the_lock_is_read_on_real_outputs(output, showing):
    assert screen.parse_keyguard_showing(output) is showing


def test_mdreaminglockscreen_alone_says_nothing():
    """The state is `isKeyguardShowing`: a dump without it is no conclusion, never « not locked »."""
    assert screen.parse_keyguard_showing("    mDreamingLockscreen=true\n") is None
    assert screen.parse_keyguard_showing("") is None


class Phone:
    """What the phone answers, one `dumpsys window` after the other, and what it was told."""

    def __init__(self, monkeypatch, *dumps):
        self.dumps = list(dumps)
        self.commands = []
        monkeypatch.setattr(screen, "_dumpsys_window", self._next_dump)
        monkeypatch.setattr(screen, "_tell_phone", lambda serial, command: self.commands.append(command))
        monkeypatch.setattr(screen, "LIFT_CHECK_DELAY_S", 0)

    def _next_dump(self, serial):
        return self.dumps.pop(0) if len(self.dumps) > 1 else self.dumps[0]


def test_a_phone_not_locked_is_told_nothing(monkeypatch):
    phone = Phone(monkeypatch, ANDROID_14_UNLOCKED)

    assert screen.phone_locked_after_lift("SERIAL") is False
    assert phone.commands == []


def test_a_lock_without_code_is_lifted_and_verified(monkeypatch):
    phone = Phone(monkeypatch, ANDROID_14_LOCKED, ANDROID_14_LOCKED, ANDROID_14_UNLOCKED)

    assert screen.phone_locked_after_lift("SERIAL") is False
    assert phone.commands == [["input", "keyevent", "KEYCODE_WAKEUP"], ["wm", "dismiss-keyguard"]]


def test_a_lock_that_stays_is_said(monkeypatch):
    """A lock with a code, or any lock the dismissal did not lift: the second reading decides."""
    Phone(monkeypatch, ANDROID_11_LOCKED)

    assert screen.phone_locked_after_lift("SERIAL") is True


def test_an_unreadable_phone_is_no_conclusion_and_is_told_nothing(monkeypatch):
    phone = Phone(monkeypatch, None)

    assert screen.phone_locked_after_lift("SERIAL") is None
    assert phone.commands == []


def test_the_reading_goes_through_the_adb_door_word_by_word(monkeypatch):
    asked = []

    def _shell(serial, command, **options):
        asked.append((serial, command))
        return subprocess.CompletedProcess(command, 0, ANDROID_14_LOCKED, "")

    monkeypatch.undo()
    monkeypatch.setattr(screen, "run_adb_shell_process", _shell)

    assert screen.read_keyguard_showing("SERIAL") is True
    assert asked == [("SERIAL", ["dumpsys", "window"])]


def test_adb_that_fails_is_no_conclusion(monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(screen, "run_adb_shell_process",
                        lambda serial, command, **options: subprocess.CompletedProcess(command, 1, "", "device offline"))

    assert screen.read_keyguard_showing("SERIAL") is None
