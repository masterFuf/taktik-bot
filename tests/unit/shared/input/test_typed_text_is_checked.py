"""What a field holds after typing is what gets sent: waited out, read back, retyped once, or refused.

`KeyboardPhone` types the way the Taktik Keyboard APK does (AdbIME 3.0.2, decompiled): the
first character lands inside the broadcast, each next one after a gap drawn in
[mean - deviation, mean + deviation] ms -- here always the slowest -- on a clock that only
`time.sleep` moves. The field is read like `device(focused=True).info`.
"""

import base64

import pytest

import taktik.core.shared.behavior.typing as typing_plan
import taktik.core.shared.input.taktik_keyboard as kb


class KeyboardPhone:
    def __init__(self, *, field="", drop_backspace=False, clear_works=True, readable=True):
        self.clock = 0.0
        self.field = field
        self.pending = []              # (time, char), in landing order
        self.drop_backspace = drop_backspace
        self.clear_works = clear_works
        self.readable = readable
        self.commands = []

    def sleep(self, seconds):
        self.clock += max(0.0, seconds)
        self._land()

    def _land(self):
        while self.pending and self.pending[0][0] <= self.clock + 1e-9:
            self.field += self.pending.pop(0)[1]

    @staticmethod
    def _arg(command, name):
        return command.split(f"{name} ", 1)[1].split(" ", 1)[0]

    def shell(self, device_id, command):
        self._land()
        if "ADB_INPUT_B64" in command:
            text = base64.b64decode(self._arg(command, "--es msg")).decode("utf-8")
            gap = (int(self._arg(command, "--ei delay_mean"))
                   + int(self._arg(command, "--ei delay_deviation"))) / 1000
            self.commands.append("type")
            self.pending += [(self.clock + i * gap, ch) for i, ch in enumerate(text)]
            self.pending.sort(key=lambda item: item[0])
            self._land()
            return "Broadcasting: Intent { act=ADB_INPUT_B64 }\nBroadcast completed: result=0"
        if command.startswith("input keyevent 67"):
            self.commands.append("del")
            if not self.drop_backspace:
                self.field = self.field[:-1]
            return ""
        if "ADB_CLEAR_TEXT" in command:
            self.commands.append("clear")
            if self.clear_works:
                self.field = ""
            return "Broadcast completed: result=0"
        return ""

    def __call__(self, **selector):
        phone = self

        class _Focused:
            @property
            def info(self):
                if not phone.readable:
                    raise RuntimeError("UiObjectNotFoundError")
                phone._land()
                return {"text": phone.field, "focused": True}

        return _Focused()


@pytest.fixture
def phone(monkeypatch):
    phone = KeyboardPhone()
    monkeypatch.setattr(kb, "run_adb_shell", phone.shell)
    monkeypatch.setattr(kb.time, "sleep", phone.sleep)
    monkeypatch.setattr(kb, "is_taktik_keyboard_active", lambda _device_id: True)
    return phone


def _plan(monkeypatch, ops):
    monkeypatch.setattr(typing_plan, "build_typing_plan", lambda text, rng=None: ops)


# --- the wait: the next command never overtakes the keyboard ------------------------------------


def test_typing_returns_only_once_the_slowest_keyboard_has_finished(phone):
    text = "Merci pour ce partage !!"  # 24 chars: the old wait ended before the last one landed
    assert kb.type_with_taktik_keyboard("dev", text, 80, 30) is True
    assert phone.pending == []
    assert phone.field == text


def test_the_wait_counts_utf16_units_like_the_keyboard():
    assert kb.typing_seconds("ab", 80, 30) == pytest.approx(0.11)
    assert kb.typing_seconds("a😂", 80, 30) == pytest.approx(0.22)  # the emoji is two units
    assert kb.typing_seconds("", 80, 30) == 0


def test_a_typo_on_a_slow_keyboard_is_erased_not_the_letter_before_it(phone, monkeypatch):
    target = "Merci pour ce partage tres utile"
    typo = target[:23] + "w"
    _plan(monkeypatch, [("type", typo), ("pause", 0.15), ("backspace", 1), ("type", target[23:])])

    assert kb.type_text_human("dev", target) is True

    assert phone.field == target


@pytest.mark.parametrize("action_class", ["shared", "instagram"])
def test_every_typing_entry_point_waits_out_the_keyboard(phone, monkeypatch, action_class):
    """The base actions each had their own broadcast and their own, shorter, wait."""
    from loguru import logger

    import taktik.core.shared.actions.base_action as shared_base
    from taktik.core.shared.actions.base_action import SharedBaseAction
    from taktik.core.social_media.instagram.actions.core.base_action import BaseAction

    monkeypatch.setattr(shared_base, "run_adb_shell", phone.shell)
    cls = SharedBaseAction if action_class == "shared" else BaseAction
    action = cls.__new__(cls)
    action.logger = logger
    action.device = phone
    action._get_device_serial = lambda: "dev"
    text = "Merci pour ce partage tres utile !"

    assert action._type_with_taktik_keyboard(text) is True

    assert phone.pending == []
    assert phone.field == text


# --- the check: the field must hold the asked text ----------------------------------------------


def test_a_lost_backspace_is_caught_and_the_text_retyped(phone, monkeypatch):
    """A backspace that does nothing leaves the typo in the field."""
    phone.drop_backspace = True
    _plan(monkeypatch, [("type", "Test TAM"), ("pause", 0.3), ("backspace", 1), ("type", "KTIK")])

    assert kb.type_text_checked(phone, "dev", "Test TAKTIK") is True

    assert phone.field == "Test TAKTIK"
    assert "clear" in phone.commands


def test_a_field_that_keeps_differing_is_refused(phone, monkeypatch):
    phone.drop_backspace = True
    phone.clear_works = False
    _plan(monkeypatch, [("type", "Test TAM"), ("pause", 0.3), ("backspace", 1), ("type", "KTIK")])

    assert kb.type_text_checked(phone, "dev", "Test TAKTIK") is False


def test_a_field_that_cannot_be_read_is_refused(phone):
    phone.readable = False
    assert kb.type_text_checked(phone, "dev", "bonjour", typos=False) is False


def test_a_correct_text_is_typed_once(phone):
    assert kb.type_text_checked(phone, "dev", "Bien vu 😂 vraiment", typos=False) is True
    assert phone.commands == ["type"]


def test_leftovers_in_the_field_are_replaced(phone):
    phone.field = "ancien brouillon"
    assert kb.type_text_checked(phone, "dev", "bonjour", typos=False) is True
    assert phone.field == "bonjour"


def test_a_reply_keeps_its_mention(phone):
    phone.field = "@ana "
    assert kb.type_text_checked(phone, "dev", "merci !", prefix="@ana ", typos=False) is True
    assert phone.field == "@ana merci !"
    assert "clear" not in phone.commands


def test_a_lost_mention_is_typed_back(phone):
    assert kb.type_text_checked(phone, "dev", "merci !", prefix="@ana ", typos=False) is True
    assert phone.field == "@ana merci !"


@pytest.mark.parametrize("read,same", [
    ("Test TAKTIK", True),
    ("Test\nTAKTIK ", True),     # a wrapped or trimmed line is the same text
    ("Test TAMKTIK", False),
    ("TestTAKTIK", False),       # a lost space is not
    ("Message…", False),         # an empty composer reads its hint
])
def test_what_counts_as_the_same_text(phone, read, same):
    phone.field = read
    assert kb.field_holds_text(phone, "Test TAKTIK") is same


class UnfocusedScreen:
    """A screen where no node reports the focus, as TikTok's DM composer once typed into."""

    def __init__(self, *texts):
        self.texts = list(texts)

    def __call__(self, **selector):
        screen = self

        class _Selection:
            @property
            def count(self):
                return len(screen.texts)

            @property
            def info(self):
                if selector.get("focused") or not screen.texts:
                    raise RuntimeError("UiObjectNotFoundError")
                return {"text": screen.texts[0], "focused": False}

        return _Selection()


def test_an_unfocused_field_is_read_when_it_is_the_only_one():
    assert kb.read_focused_text(UnfocusedScreen("hello there")) == "hello there"
    assert kb.field_holds_text(UnfocusedScreen("hello there"), "hello there")


def test_two_unfocused_fields_are_not_guessed():
    assert kb.read_focused_text(UnfocusedScreen("hello there", "search")) is None
    assert not kb.field_holds_text(UnfocusedScreen("hello there", "search"), "hello there")


def test_no_field_at_all_reads_nothing():
    assert kb.read_focused_text(UnfocusedScreen()) is None
