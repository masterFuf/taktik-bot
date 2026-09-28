"""The phone's keyboard is checked at each broadcast of text, not trusted for two minutes.

`is_taktik_keyboard_active` kept a phone "on Taktik Keyboard" for 120 s after a look or a typed
text, and every text typed in the meantime renewed it. uiautomator2 switches the phone to its OWN
keyboard for `send_keys`, `clear_text` and `hide_keyboard` (the login's paste, the fallback that
empties a field): the Taktik Keyboard service is then unbound, its receiver gone, and the next text
broadcast in the two minutes reached no one while the typing said it had typed. The same for the
broadcast that empties a field, which never looked at the keyboard at all.

The phone below answers in the words of a Pixel 4a (Android 13, `fixtures/ime_answers_android13.json`)
and models what the tests need of it: its input method, the Taktik Keyboard receiving a broadcast
only while it is the input method, and its shell running a command that reads the keyboard and
branches (checked on the Pixel 4a on 2026-09-28: the shell answers the branch taken).
"""

import base64
import json
from pathlib import Path

import pytest

from taktik.core.shared.input import taktik_keyboard as kb
from unit.android_shell import READ_KEYBOARD, is_keyboard_check, run_keyboard_check

_RECORDED = json.loads(
    (Path(__file__).parent / "fixtures" / "ime_answers_android13.json").read_text(encoding="utf-8"))
ANSWERS = _RECORDED["answers"]

TAKTIK = kb.TAKTIK_KEYBOARD_IME
GBOARD = kb.GBOARD_IME
BROADCAST_ANSWER = "Broadcasting: Intent { act=ADB_INPUT_B64 flg=0x400000 (has extras) }\nBroadcast completed: result=0"


class Pixel4a:
    """`run_adb_shell` of a phone on the input method `current`, Taktik Keyboard installed."""

    def __init__(self, current=TAKTIK):
        self.current = current
        self.commands = []
        self.typed = []      # texts the Taktik Keyboard received
        self.lost = []       # texts broadcast while the phone was on another keyboard
        self.clears = []     # True: received by the Taktik Keyboard; False: lost

    def __call__(self, device_id, command):
        self.commands.append(command)
        return self._run(command)

    def _run(self, command):
        if is_keyboard_check(command):
            return run_keyboard_check(command, self.current, self._run)
        if command == READ_KEYBOARD:
            return self.current
        if command.startswith("ime enable "):
            return ANSWERS["ime_enable_taktik"]
        if command.startswith("ime set "):
            self.current = command[len("ime set "):]
            return ANSWERS["ime_set_taktik"].replace(TAKTIK, self.current)
        if command == "dumpsys input_method":
            return ANSWERS["dumpsys_input_method_bound"] if self.current == TAKTIK else ""
        if command.startswith("am broadcast -a ADB_INPUT_B64 --es msg "):
            text = base64.b64decode(command.split("--es msg ", 1)[1].split(" ", 1)[0]).decode("utf-8")
            (self.typed if self.current == TAKTIK else self.lost).append(text)
            return BROADCAST_ANSWER
        if command == "am broadcast -a ADB_CLEAR_TEXT":
            self.clears.append(self.current == TAKTIK)
            return "Broadcasting: Intent { act=ADB_CLEAR_TEXT flg=0x400000 }\nBroadcast completed: result=0"
        return ""


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(kb, "_original_ime", {})
    monkeypatch.setattr(kb, "_atexit_registered", True)
    monkeypatch.setattr(kb.time, "sleep", lambda _s: None)


def _on(monkeypatch, phone):
    monkeypatch.setattr(kb, "run_adb_shell", phone)
    return phone


def test_a_text_typed_after_uiautomator2_took_the_keyboard_still_reaches_the_field(monkeypatch):
    phone = _on(monkeypatch, Pixel4a(current=TAKTIK))
    assert kb.type_with_taktik_keyboard("4a-uiautomator", "bonjour") is True

    phone.current = kb.UIAUTOMATOR_IME     # uiautomator2's send_keys / clear_text, seconds later

    assert kb.type_with_taktik_keyboard("4a-uiautomator", "encore") is True
    assert phone.lost == []
    assert phone.typed == ["bonjour", "encore"]
    assert phone.current == TAKTIK


def test_a_text_the_keyboard_cannot_take_back_is_not_said_typed(monkeypatch):
    """uiautomator2 holds the keyboard and Android refuses Taktik's: nothing typed, and it says so."""
    phone = _on(monkeypatch, Pixel4a(current=TAKTIK))
    assert kb.type_with_taktik_keyboard("4a-refused", "bonjour") is True
    phone.current = kb.UIAUTOMATOR_IME
    monkeypatch.setattr(kb, "activate_taktik_keyboard", lambda _device_id: False)

    assert kb.type_with_taktik_keyboard("4a-refused", "encore") is False
    assert phone.lost == []


def test_emptying_a_field_while_uiautomator2_holds_the_keyboard_is_not_said_done(monkeypatch):
    phone = _on(monkeypatch, Pixel4a(current=kb.UIAUTOMATOR_IME))

    assert kb.clear_text_with_taktik_keyboard("4a-clear-lost") is False
    assert phone.clears == []


def test_emptying_a_field_on_the_keyboard_is_done(monkeypatch):
    phone = _on(monkeypatch, Pixel4a(current=TAKTIK))

    assert kb.clear_text_with_taktik_keyboard("4a-clear") is True
    assert phone.clears == [True]


def test_the_check_costs_no_adb_command(monkeypatch):
    """Each text is ONE adb command: the phone's shell reads its keyboard and broadcasts."""
    phone = _on(monkeypatch, Pixel4a(current=TAKTIK))

    assert kb.type_with_taktik_keyboard("4a-cost", "un") is True
    assert kb.type_with_taktik_keyboard("4a-cost", "deux") is True
    assert len(phone.commands) == 2
    assert phone.typed == ["un", "deux"]


def test_the_phone_s_keyboard_is_remembered_from_the_check(monkeypatch):
    """The first check tells which keyboard the session gives back, without a read of its own."""
    samsung = "com.samsung.android.honeyboard/.service.HoneyBoardService"
    phone = _on(monkeypatch, Pixel4a(current=samsung))

    assert kb.type_with_taktik_keyboard("a6", "bonjour") is True
    assert phone.typed == ["bonjour"]
    assert kb._original_ime == {"a6": samsung}
    # The one plain read is the switch checking that the phone is on Taktik Keyboard.
    assert phone.commands.count(READ_KEYBOARD) == 1
    assert kb.restore_original_keyboard("a6") is True
    assert phone.current == samsung
