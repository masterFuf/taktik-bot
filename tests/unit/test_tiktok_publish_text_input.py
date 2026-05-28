import subprocess

from taktik.core.social_media.tiktok.services.publish_text_input import (
    clear_caption_text,
    escape_adb_input_text,
    type_ascii_text_with_adb,
    type_caption_text,
)


def completed(returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr=stderr)


def test_clear_caption_text_activates_keyboard_then_clears():
    calls = []

    assert clear_caption_text(
        "device-1",
        activate_keyboard=lambda device_id: calls.append(("activate", device_id)),
        clear_keyboard=lambda device_id: calls.append(("clear", device_id)) or True,
    )
    assert calls == [("activate", "device-1"), ("clear", "device-1")]


def test_type_caption_text_returns_true_for_empty_text_without_input():
    assert type_caption_text("device-1", "", type_keyboard=lambda *_args, **_kwargs: False)


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


def test_type_caption_text_falls_back_to_adb_for_ascii_when_keyboard_fails():
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return completed()

    assert type_caption_text(
        "device-1",
        "hi there &|;",
        type_keyboard=lambda *_args, **_kwargs: False,
        run=fake_run,
    )

    assert calls[0][0] == [
        "adb",
        "-s",
        "device-1",
        "shell",
        "input",
        "text",
        "hi%sthere%s\\&\\|\\;",
    ]
    assert calls[0][1]["timeout"] == 8


def test_type_caption_text_does_not_use_adb_for_non_ascii_fallback():
    calls = []

    assert not type_caption_text(
        "device-1",
        "caf\u00e9 accentu\u00e9",
        type_keyboard=lambda *_args, **_kwargs: False,
        run=lambda *args, **kwargs: calls.append((args, kwargs)) or completed(),
    )
    assert calls == []


def test_type_ascii_text_with_adb_reports_non_zero_exit_as_false():
    messages = []

    assert not type_ascii_text_with_adb(
        "device-1",
        "hello",
        run=lambda *_args, **_kwargs: completed(returncode=1, stderr="bad input"),
        log=lambda level, message: messages.append((level, message)),
    )
    assert messages == [("debug", "[caption] adb input text failed: bad input")]


def test_escape_adb_input_text_preserves_existing_behavior():
    assert escape_adb_input_text("a b\\c&|;") == "a%sb\\\\c\\&\\|\\;"
