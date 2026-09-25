"""A DM counts as sent only when the composer is back to empty (or its placeholder) or when the
bubble shows up in the conversation. A composer that merely CHANGED proves nothing: a keyboard
suggestion rewrites the draft, an Enter adds a line, a sheet raised by a wrong tap hides the field.

The phone below renders a conversation the way the device dumps it (43.1.4 and 46.9.3 shapes:
the field shows its placeholder as text with an equal hint, a typed draft with an empty hint),
evaluated by uiautomator2's own `d.xpath()` engine. Texts are invented.
"""

import time
import types

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.conversation import CONVERSATION_SELECTORS

PLACEHOLDER = "Message…"


def _n(cls, attrs="", children=""):
    cls = cls if "." in cls else f"android.widget.{cls}"
    return f'<node class="{cls}" resource-id="" bounds="[0,0][10,10]" {attrs}>{children}</node>'


class _Phone:
    wait_timeout = 1.0

    def __init__(self, draft):
        self.composer = draft
        self.bubbles = ["Bonjour"]
        self.sheet_over_conversation = False
        self.on_enter = lambda phone: None
        self.xpath = XPathEntry(self)

    def press(self, key):
        assert key == "enter"
        self.on_enter(self)

    @staticmethod
    def _bubble(text):
        label = _n("X.a1b2", f'text="{text}" content-desc="" focusable="true"')
        tap = _n("FrameLayout", 'clickable="true"', label)
        return _n("ViewGroup", children=_n("FrameLayout", 'long-clickable="true"', tap))

    def dump_hierarchy(self, *a, **k):
        rows = "".join(self._bubble(text) for text in self.bubbles)
        conversation = _n("androidx.recyclerview.widget.RecyclerView", 'clickable="true"', rows)
        if self.sheet_over_conversation:
            sheet = _n("FrameLayout", 'content-desc="Galerie"')
            return f'<hierarchy rotation="0">{sheet}</hierarchy>'
        text = self.composer or PLACEHOLDER
        hint = PLACEHOLDER if not self.composer else ""
        field = _n("EditText", f'text="{text}" hint="{hint}" content-desc="" clickable="true"')
        return f'<hierarchy rotation="0">{conversation}{_n("ViewGroup", children=_n("FrameLayout", children=field))}</hierarchy>'


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    set_active_locale("fr")
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    yield
    set_active_locale(None)


def _actions(phone, send_button_found):
    dm = DMActions.__new__(DMActions)
    dm.device = phone
    dm.conversation_selectors = CONVERSATION_SELECTORS
    dm.logger = types.SimpleNamespace(debug=lambda *a, **k: None, warning=lambda *a, **k: None)
    dm._find_and_click = lambda selectors, timeout=2: send_button_found(phone)
    return dm


def _sent(phone):
    phone.bubbles.append(phone.composer)
    phone.composer = ""
    return True


def test_a_send_that_empties_the_composer_is_a_send():
    phone = _Phone("Salut toi")
    assert _actions(phone, _sent).send_message() is True


def test_a_bubble_that_appears_is_a_send_even_if_the_draft_stays():
    def sent_but_kept(phone):
        phone.bubbles.append(phone.composer)
        return True

    assert _actions(_Phone("Salut toi"), sent_but_kept).send_message() is True


def test_an_enter_that_adds_a_line_is_not_a_send():
    phone = _Phone("Salut toi")
    phone.on_enter = lambda p: setattr(p, "composer", p.composer + "&#10;")
    assert _actions(phone, lambda p: False).send_message() is False


def test_a_keyboard_that_rewrites_the_draft_is_not_a_send():
    phone = _Phone("brouillon non envoye")
    phone.on_enter = lambda p: setattr(p, "composer", "brouillon non envoyé")
    assert _actions(phone, lambda p: False).send_message() is False


def test_a_tap_that_hides_the_composer_is_not_a_send():
    def opens_a_sheet(phone):
        phone.sheet_over_conversation = True
        return True

    assert _actions(_Phone("Salut toi"), opens_a_sheet).send_message() is False


def test_a_composer_showing_only_its_placeholder_sends_nothing():
    taps = []
    phone = _Phone("")
    assert _actions(phone, lambda p: taps.append(p) or True).send_message() is False
    assert taps == []
