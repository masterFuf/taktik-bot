"""A TikTok caption is typed by Taktik Keyboard, or the fill fails: nothing is pasted.

When the keyboard could not type, the caption and each hashtag fell back on `adb shell input text`
(ASCII only): the whole text written at once, through no keyboard, a signal no person gives. The
caption path starts every process through `subprocess.Popen`; `adb_processes` records each one
instead of starting adb.
"""

import subprocess

import pytest

from taktik.core.shared.input import taktik_keyboard as kb
from taktik.core.social_media.tiktok.services.publish.text_input import (
    clear_caption_text,
    type_caption_checked,
    type_caption_text,
)


class _RecordedProcess:
    """Stands for a started process: its command line is recorded, it answers like a successful adb."""

    started: list = []

    def __init__(self, args, **_kwargs):
        self.args = args
        self.returncode = 0
        _RecordedProcess.started.append(list(args))

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def communicate(self, input=None, timeout=None):
        return "", ""

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0

    def kill(self):
        return None


@pytest.fixture
def adb_processes(monkeypatch):
    started = []
    monkeypatch.setattr(_RecordedProcess, "started", started)
    monkeypatch.setattr(subprocess, "Popen", _RecordedProcess)
    return started


def _keyboard_types_nothing(*_args, **_kwargs):
    return False


def _keyboard_breaks(*_args, **_kwargs):
    raise RuntimeError("adb gone")


# -- Clear ----------------------------------------------------------------------------------------

def test_clear_caption_text_activates_keyboard_then_clears():
    calls = []

    assert clear_caption_text(
        "device-1",
        activate_keyboard=lambda device_id: calls.append(("activate", device_id)) or True,
        clear_keyboard=lambda device_id: calls.append(("clear", device_id)) or True,
    )
    assert calls == [("activate", "device-1"), ("clear", "device-1")]


def test_a_caption_is_not_cleared_when_the_keyboard_cannot_be_activated():
    """The clear broadcast reached no receiver and the field passed for cleared."""
    cleared = []

    assert clear_caption_text(
        "device-1",
        activate_keyboard=lambda _device_id: False,
        clear_keyboard=lambda device_id: cleared.append(device_id) or True,
    ) is False
    assert cleared == []


# -- Hashtags (typed one by one, not read back) ---------------------------------------------------

def test_type_caption_text_returns_true_for_empty_text_without_input():
    assert type_caption_text("device-1", "", type_keyboard=_keyboard_types_nothing)


def test_type_caption_text_uses_taktik_keyboard_first():
    calls = []

    assert type_caption_text(
        "device-1",
        "hello",
        delay_mean=70,
        delay_deviation=10,
        type_keyboard=lambda *args, **kwargs: calls.append((args, kwargs)) or True,
    )

    assert calls == [(("device-1", "hello"), {"delay_mean": 70, "delay_deviation": 10})]


@pytest.mark.parametrize("keyboard", [_keyboard_types_nothing, _keyboard_breaks], ids=["fails", "raises"])
def test_a_hashtag_the_keyboard_cannot_type_is_not_pasted(adb_processes, keyboard):
    logs = []

    assert type_caption_text(
        "device-1", " #paris", type_keyboard=keyboard, log=lambda level, message: logs.append(level),
    ) is False

    assert adb_processes == []
    assert "error" in logs


# -- The caption (read back) ----------------------------------------------------------------------

def test_a_caption_the_keyboard_cannot_type_is_not_pasted(monkeypatch, adb_processes):
    """The keyboard could not make the field hold the caption (`type_text_checked` read it back)."""
    monkeypatch.setattr(kb, "type_text_checked", lambda *_a, **_k: False)
    monkeypatch.setattr(kb, "activate_taktik_keyboard", lambda _device_id: False)
    monkeypatch.setattr(kb, "clear_text_with_taktik_keyboard", lambda _device_id: True)
    monkeypatch.setattr(kb, "field_holds_text", lambda _device, _text: False)

    assert type_caption_checked(object(), "device-1", "hello there") is False

    assert adb_processes == []
