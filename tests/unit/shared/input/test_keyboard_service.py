"""The Taktik Keyboard service a host hands to a run: the serial of its phone, and typing through the
bot's keyboard (`shared/input/taktik_keyboard.py` owns the IME and adb behaviour).

What it answers is pinned here, on doubles of the keyboard primitives (no device, no adb).
"""

import pytest

from taktik.core.shared.input import keyboard


class _Keyboard:
    """The keyboard primitives, recorded: active or not, activation that works or not, typing."""

    def __init__(self, active=True, activates=True, types=True, raises=None):
        self.active, self.activates, self.types, self.raises = active, activates, types, raises
        self.calls = []

    def is_active(self, device_id):
        self.calls.append(("active?", device_id))
        if self.raises == "active?":
            raise OSError("adb gone")
        return self.active

    def activate(self, device_id):
        self.calls.append(("activate", device_id))
        return self.activates

    def type(self, device_id, text, delay_mean, delay_deviation):
        self.calls.append(("type", device_id, text, delay_mean, delay_deviation))
        if self.raises == "type":
            raise OSError("broadcast lost")
        return self.types

    def install(self, monkeypatch):
        monkeypatch.setattr(keyboard, "is_taktik_keyboard_active", self.is_active)
        monkeypatch.setattr(keyboard, "activate_taktik_keyboard", self.activate)
        monkeypatch.setattr(keyboard, "type_with_taktik_keyboard", self.type)
        return self


def test_the_service_carries_the_serial_of_its_phone():
    assert keyboard.KeyboardService("SERIAL").device_id == "SERIAL"


def test_an_active_keyboard_is_not_activated_again(monkeypatch):
    kb = _Keyboard(active=True).install(monkeypatch)

    assert keyboard.KeyboardService("SERIAL").ensure_active() is True
    assert kb.calls == [("active?", "SERIAL")]


def test_an_inactive_keyboard_is_activated(monkeypatch):
    kb = _Keyboard(active=False).install(monkeypatch)

    assert keyboard.KeyboardService("SERIAL").ensure_active() is True
    assert kb.calls == [("active?", "SERIAL"), ("activate", "SERIAL")]


def test_a_keyboard_that_cannot_be_activated_is_a_failure(monkeypatch):
    _Keyboard(active=False, activates=False).install(monkeypatch)

    assert keyboard.KeyboardService("SERIAL").ensure_active() is False


def test_an_unreadable_keyboard_is_a_failure(monkeypatch):
    _Keyboard(raises="active?").install(monkeypatch)

    assert keyboard.KeyboardService("SERIAL").ensure_active() is False


def test_no_text_is_typed_at_once(monkeypatch):
    kb = _Keyboard().install(monkeypatch)

    assert keyboard.KeyboardService("SERIAL").type_text("") is True
    assert kb.calls == []


def test_the_text_goes_through_the_bot_keyboard_at_the_given_pace(monkeypatch):
    kb = _Keyboard(active=True).install(monkeypatch)

    assert keyboard.KeyboardService("SERIAL").type_text("Salut ça va ?", delay_mean=60, delay_deviation=10) is True
    assert kb.calls == [("active?", "SERIAL"), ("type", "SERIAL", "Salut ça va ?", 60, 10)]


def test_the_default_pace(monkeypatch):
    kb = _Keyboard().install(monkeypatch)

    keyboard.KeyboardService("SERIAL").type_text("x")

    assert kb.calls[-1] == ("type", "SERIAL", "x", 80, 30)


def test_nothing_is_typed_without_the_keyboard(monkeypatch):
    kb = _Keyboard(active=False, activates=False).install(monkeypatch)

    assert keyboard.KeyboardService("SERIAL").type_text("hello") is False
    assert not any(call[0] == "type" for call in kb.calls)


@pytest.mark.parametrize("types, verdict", [(True, True), (False, False)])
def test_the_verdict_is_the_one_of_the_typing(monkeypatch, types, verdict):
    _Keyboard(types=types).install(monkeypatch)

    assert keyboard.KeyboardService("SERIAL").type_text("hello") is verdict


def test_typing_that_fails_is_a_failure(monkeypatch):
    _Keyboard(raises="type").install(monkeypatch)

    assert keyboard.KeyboardService("SERIAL").type_text("hello") is False
