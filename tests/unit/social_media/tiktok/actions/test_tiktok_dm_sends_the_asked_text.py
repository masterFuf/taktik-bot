"""A TikTok DM leaves only when the composer holds exactly the asked text.

A backspace correcting a typo can be lost. The phone below drops every backspace; its composer
is read over `device(focused=True).info` and dumped for the send confirmation.
"""

import base64
import time
import types

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.behavior.typing as typing_plan
import taktik.core.shared.input.taktik_keyboard as kb
from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.conversation import CONVERSATION_SELECTORS

PLACEHOLDER = "Message…"


def _n(cls, attrs="", children=""):
    cls = cls if "." in cls else f"android.widget.{cls}"
    return f'<node class="{cls}" resource-id="" bounds="[0,0][10,10]" {attrs}>{children}</node>'


class _Phone:
    wait_timeout = 1.0
    device_id = "PIXEL-6A"

    def __init__(self, composer=""):
        self.composer = composer
        self.sent = []
        self.xpath = XPathEntry(self)

    def shell(self, device_id, command):
        if "ADB_INPUT_B64" in command:
            b64 = command.split("--es msg ", 1)[1].split(" ", 1)[0]
            self.composer += base64.b64decode(b64).decode("utf-8")
            return "Broadcast completed: result=0"
        if "ADB_CLEAR_TEXT" in command:
            self.composer = ""
            return "Broadcast completed: result=0"
        return ""  # `input keyevent 67`: dropped

    def __call__(self, **selector):
        phone = self
        return types.SimpleNamespace(info={"text": phone.composer or PLACEHOLDER, "focused": True})

    def dump_hierarchy(self, *a, **k):
        rows = "".join(
            _n("ViewGroup", children=_n("FrameLayout", 'long-clickable="true"', _n(
                "FrameLayout", 'clickable="true"', _n("X.a1b2", f'text="{text}" focusable="true"'))))
            for text in self.sent)
        conversation = _n("androidx.recyclerview.widget.RecyclerView", 'clickable="true"', rows)
        text = self.composer or PLACEHOLDER
        hint = PLACEHOLDER if not self.composer else ""
        field = _n("EditText", f'text="{text}" hint="{hint}" content-desc="" clickable="true"')
        return f'<hierarchy rotation="0">{conversation}{_n("ViewGroup", children=field)}</hierarchy>'


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    set_active_locale("fr")
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    monkeypatch.setattr(kb, "is_taktik_keyboard_active", lambda _device_id: True)
    yield
    set_active_locale(None)


def _actions(phone, monkeypatch):
    monkeypatch.setattr(kb, "run_adb_shell", phone.shell)
    dm = DMActions.__new__(DMActions)
    dm.device = phone
    dm.conversation_selectors = CONVERSATION_SELECTORS
    dm.logger = types.SimpleNamespace(debug=lambda *a, **k: None, warning=lambda *a, **k: None,
                                      error=lambda *a, **k: None)
    dm._clear_text_with_taktik_keyboard = lambda: bool(phone.shell(phone.device_id, "am broadcast -a ADB_CLEAR_TEXT"))

    def find_and_click(selectors, timeout=2):
        if selectors == CONVERSATION_SELECTORS.send_button:
            phone.sent.append(phone.composer)
            phone.composer = ""
        return True

    dm._find_and_click = find_and_click
    return dm


def test_a_dm_whose_backspace_is_lost_goes_out_as_asked(monkeypatch):
    phone = _Phone()
    monkeypatch.setattr(typing_plan, "build_typing_plan", lambda text, rng=None: [
        ("type", "Test TAM"), ("pause", 0.3), ("backspace", 1), ("type", "KTIK")])

    assert _actions(phone, monkeypatch).send_text_message("Test TAKTIK") is True

    assert phone.sent == ["Test TAKTIK"]


def test_a_composer_holding_another_text_is_not_sent(monkeypatch):
    phone = _Phone(composer="Test TAMKTIK")

    assert _actions(phone, monkeypatch).send_message(expected="Test TAKTIK") is False

    assert phone.sent == []


class _UnclearablePhone(_Phone):
    """A composer the keyboard cannot empty: the exact retype lands after the typo."""

    def shell(self, device_id, command):
        return "" if "ADB_CLEAR_TEXT" in command else super().shell(device_id, command)


def test_a_message_that_cannot_be_typed_right_is_not_sent(monkeypatch):
    phone = _UnclearablePhone()
    monkeypatch.setattr(typing_plan, "build_typing_plan", lambda text, rng=None: [
        ("type", "Test TAM"), ("pause", 0.3), ("backspace", 1), ("type", "KTIK")])

    assert _actions(phone, monkeypatch).send_text_message("Test TAKTIK") is False

    assert phone.sent == []
