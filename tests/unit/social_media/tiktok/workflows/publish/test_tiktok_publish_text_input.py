import subprocess

from taktik.core.social_media.tiktok.services.publish.text_input import (
    caption_text_matches,
    clear_caption_text,
    escape_adb_input_text,
    focus_caption_field,
    read_caption_field_text,
    type_ascii_text_with_adb,
    type_caption_text,
)


class FakeCaptionField:
    def __init__(self, text="Add description...", *, hint="Add description...", accepts_text=True):
        self.text = text
        self.hint = hint
        self.accepts_text = accepts_text
        self.clicks = 0
        self.focused = False

    @property
    def info(self):
        return {"text": self.text, "hint": self.hint, "focused": self.focused}

    def click(self):
        self.clicks += 1
        self.focused = True

    def get_text(self):
        return self.text

    def set_text(self, text):
        if self.accepts_text:
            self.text = text
        return self.accepts_text


class FakeCaptionDevice:
    def __init__(self, field=None):
        self.field = field

    class _XPath:
        def __init__(self, field):
            self.field = field

        def wait(self, timeout=0):
            return self.field is not None

        def __bool__(self):
            return self.field is not None

        def __getattr__(self, name):
            return getattr(self.field, name)

    def xpath(self, _selector):
        return self._XPath(self.field)


def test_focus_caption_field_clicks_the_actual_editable_before_input():
    field = FakeCaptionField()

    focused = focus_caption_field(FakeCaptionDevice(field), selectors=["//caption"], timeout=0)

    assert focused is not None
    assert field.clicks == 1
    assert field.focused is True


def test_read_caption_field_text_treats_visible_hint_as_empty():
    field = FakeCaptionField()
    assert read_caption_field_text(field) == ""


def test_caption_text_matches_requires_caption_and_every_expected_hashtag():
    assert caption_text_matches(
        "Angels — explained in under a minute. #stickman #animation",
        "Angels — explained in under a minute.",
        ["stickman", "animation"],
    )
    assert not caption_text_matches(
        "Angels — explained in under a minute. #stickman",
        "Angels — explained in under a minute.",
        ["stickman", "animation"],
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


def test_keyboard_ack_log_never_claims_text_was_inserted():
    messages = []

    assert type_caption_text(
        "device-1",
        "hello",
        type_keyboard=lambda *_args, **_kwargs: True,
        log=lambda level, message: messages.append((level, message)),
    )

    assert messages == [("debug", "[caption] Taktik Keyboard command accepted; awaiting UI verification")]


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
