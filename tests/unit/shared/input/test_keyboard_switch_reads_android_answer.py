"""A keyboard switch counts only when Android selected that input method and the phone is on it.

The switch to Taktik Keyboard and the give-back of the phone's keyboard read `"selected" in answer`.
Android refuses an input method the phone does not have with "Unknown input method <id> cannot be
selected for user #0", which contains "selected": the refusal passed for a switch. On a phone
without Taktik Keyboard the text broadcast then reached no receiver, and the unchecked typing
(`type_with_taktik_keyboard`, under `type_text`) said it had typed.

The phone below answers each `ime` command in the words of a Pixel 4a (Android 13), recorded in
`fixtures/ime_answers_android13.json`: the success for an input method it has, the refusal for one
it has not (recorded with an id no phone has; the same sentence, the id swapped).
"""

import json
from pathlib import Path

import pytest

from taktik.core.shared.actions.base_action import SharedBaseAction
from taktik.core.shared.device import adb
from taktik.core.shared.input import taktik_keyboard as kb
from unit.android_shell import is_keyboard_check, run_keyboard_check

_RECORDED = json.loads(
    (Path(__file__).parent / "fixtures" / "ime_answers_android13.json").read_text(encoding="utf-8"))
ANSWERS = _RECORDED["answers"]
RECORDED_ABSENT = _RECORDED["absent_ime"]

TAKTIK = kb.TAKTIK_KEYBOARD_IME
GBOARD = kb.GBOARD_IME
SAMSUNG = "com.samsung.android.honeyboard/.service.HoneyBoardService"


class Android13Phone:
    """`run_adb_shell` of a phone that has the input methods `installed` and is on `current`.

    `stays_on`: the phone answers that it selected an input method but stays on this one (the
    answer and the phone's state disagree)."""

    def __init__(self, installed, current=GBOARD, stays_on=None):
        self.installed = set(installed)
        self.current = current
        self.stays_on = stays_on
        self.commands = []
        self.sent = []   # broadcasts the phone's shell ran (a keyboard check may hold one back)

    def __call__(self, device_id, command):
        self.commands.append(command)
        return self._run(command)

    def _run(self, command):
        if is_keyboard_check(command):
            return run_keyboard_check(command, self.current, self._run)
        if command == "settings get secure default_input_method":
            return self.current
        if command == "ime list -s":
            return "\n".join(sorted(self.installed))
        if command.startswith("ime enable "):
            ime = command[len("ime enable "):]
            if ime in self.installed:
                return ANSWERS["ime_enable_taktik"].replace(TAKTIK, ime)
            return ANSWERS["ime_enable_absent"].replace(RECORDED_ABSENT, ime)
        if command.startswith("ime set "):
            ime = command[len("ime set "):]
            if ime not in self.installed:
                return ANSWERS["ime_set_absent"].replace(RECORDED_ABSENT, ime)
            self.current = self.stays_on or ime
            return ANSWERS["ime_set_taktik"].replace(TAKTIK, ime)
        if command == "dumpsys input_method":
            return ANSWERS["dumpsys_input_method_bound"] if self.current == TAKTIK else ""
        if command.startswith("am broadcast"):
            self.sent.append(command)
            # Android's usual answer, which says nothing of the keyboard receiving it (not recorded:
            # no text was sent to the Pixel 4a).
            return "Broadcasting: Intent { act=ADB_INPUT_B64 flg=0x400000 (has extras) }\nBroadcast completed: result=0"
        return ""

    @property
    def broadcasts(self):
        return self.sent


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(kb, "_original_ime", {})
    monkeypatch.setattr(kb, "_atexit_registered", True)
    monkeypatch.setattr(kb.time, "sleep", lambda _s: None)


def _on(monkeypatch, phone):
    monkeypatch.setattr(kb, "run_adb_shell", phone)
    return phone


# -- Android's answer, read exactly ---------------------------------------------------------------

def test_android_s_refusal_is_not_a_selection():
    assert kb._android_selected(ANSWERS["ime_set_absent"], RECORDED_ABSENT) is False
    assert kb._android_selected(ANSWERS["ime_set_taktik"], TAKTIK) is True
    assert kb._android_selected(ANSWERS["ime_set_gboard"], TAKTIK) is False   # another input method
    assert kb._android_selected("", TAKTIK) is False


# -- The switch to Taktik Keyboard ----------------------------------------------------------------

def test_a_phone_without_taktik_keyboard_is_not_switched(monkeypatch):
    phone = _on(monkeypatch, Android13Phone(installed={GBOARD}))

    assert kb.activate_taktik_keyboard("4a") is False
    assert phone.current == GBOARD


def test_the_unchecked_typing_types_nothing_on_a_phone_without_taktik_keyboard(monkeypatch):
    """`type_text` (a caption, a signup field) is not read back: it trusted this answer."""
    phone = _on(monkeypatch, Android13Phone(installed={GBOARD}))

    assert kb.type_with_taktik_keyboard("4a", "bonjour") is False
    assert phone.broadcasts == []


def test_a_switch_the_phone_does_not_show_is_not_a_switch(monkeypatch):
    phone = _on(monkeypatch, Android13Phone(installed={GBOARD, TAKTIK}, stays_on=GBOARD))

    assert kb.activate_taktik_keyboard("4a") is False
    assert kb.type_with_taktik_keyboard("4a", "bonjour") is False
    assert phone.broadcasts == []


def test_a_phone_with_taktik_keyboard_is_switched_then_given_its_keyboard_back(monkeypatch):
    phone = _on(monkeypatch, Android13Phone(installed={GBOARD, TAKTIK}))

    assert kb.activate_taktik_keyboard("4a") is True
    assert phone.current == TAKTIK
    assert kb.restore_original_keyboard("4a") is True
    assert phone.current == GBOARD


# -- The give-back of the phone's keyboard --------------------------------------------------------

def test_a_keyboard_android_refuses_is_not_given_back(monkeypatch):
    """The phone's own keyboard went away during the session: Android refuses it."""
    phone = _on(monkeypatch, Android13Phone(installed={SAMSUNG, TAKTIK}, current=SAMSUNG))
    assert kb.activate_taktik_keyboard("a6") is True
    phone.installed.discard(SAMSUNG)

    assert kb.restore_original_keyboard("a6") is False
    assert phone.current == TAKTIK


# -- Emptying a field from an action (SharedBaseAction) -------------------------------------------
# The Instagram search empties its field this way before each username (`search_navigation`), and
# `clear_text_field` falls back on uiautomator2's clear only when this one says it did not empty.

def _action():
    action = SharedBaseAction.__new__(SharedBaseAction)
    action.logger = kb.logger
    action._get_device_serial = lambda: "4a"
    return action


def _on_every_adb_path(monkeypatch, phone):
    """The phone behind `run_adb_shell` wherever it was imported (the action imported its own)."""
    monkeypatch.setattr(adb, "_run_adb_shell", phone)
    return phone


def test_an_action_does_not_say_a_field_emptied_on_a_phone_without_taktik_keyboard(monkeypatch):
    phone = _on_every_adb_path(monkeypatch, Android13Phone(installed={GBOARD}))

    assert _action()._clear_text_with_taktik_keyboard() is False
    assert phone.broadcasts == []
    assert phone.current == GBOARD
    # It tried the switch (`ensure_taktik_keyboard`), and stopped there: no clear was even tried.
    assert f"ime set {TAKTIK}" in phone.commands
    assert not any(is_keyboard_check(command) for command in phone.commands)


def test_an_action_empties_a_field_through_the_keyboard_it_switched_to(monkeypatch):
    phone = _on_every_adb_path(monkeypatch, Android13Phone(installed={GBOARD, TAKTIK}))

    assert _action()._clear_text_with_taktik_keyboard() is True
    assert phone.current == TAKTIK
    assert phone.broadcasts == [f"am broadcast -a {kb.IME_CLEAR_TEXT}"]
