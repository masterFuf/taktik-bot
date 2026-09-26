"""The message banner is swiped away only when it is really there, at the top of the screen.

The French entry of `popup.notification_banner` was any clickable « Répondre ». Replayed on the
captured TikTok screens, it answered on every comment sheet and every DM conversation (the reply
buttons of their rows) and on neither of the two real banners, whose « Répondre » is a plain label.
`dismiss_notification_banner` then swiped up over the top of the screen, on a sheet or a list.

The banner below is an extract of a capture (TikTok 46.6.3, French): structure, ids and bounds of
the capture, sender name invented. The comment sheet is the anonymized 47.0.3 capture of the
fixtures folder. Evaluated by uiautomator2's own `d.xpath()` engine.
"""

from pathlib import Path

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.actions.atomic.interaction.popup_actions import PopupActions
from taktik.core.social_media.tiktok.actions.core.utils import first_matching
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.shell.popups import POPUP_SELECTORS

ID = "com.zhiliaoapp.musically:id/"
SHEET_4703 = (Path(__file__).parents[1] / "fixtures" / "tt4703_fr_comment_sheet.xml").read_text(
    encoding="utf-8")


def _node(cls, rid="", text="", clickable=False, bounds="[0,0][1,1]", children=""):
    head = (f'class="{cls}" resource-id="{rid and ID + rid}" text="{text}" content-desc="" '
            f'clickable="{str(clickable).lower()}" bounds="{bounds}"')
    return f"<node {head}>{children}</node>" if children else f"<node {head}/>"


def _screen(*body):
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            f'<node class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">{"".join(body)}</node>'
            "</hierarchy>")


def _banner(message, reply="Répondre", shift=0):
    """The banner row of 46.6.3: avatar, sender and message, then the reply label in its own
    clickable frame. `shift` moves it down the screen, which no capture shows."""
    def b(left, top, right, bottom):
        return f"[{left},{top + shift}][{right},{bottom + shift}]"

    return _node("android.widget.FrameLayout", "uh0", clickable=True, bounds=b(0, 132, 1080, 561), children=(
        _node("android.view.ViewGroup", "l61", bounds=b(21, 158, 1059, 377), children=(
            _node("android.widget.LinearLayout", "l66", bounds=b(21, 158, 1059, 377), children=(
                _node("android.widget.FrameLayout", "l64", clickable=True, bounds=b(21, 158, 205, 377),
                      children=_node("android.widget.ImageView", "l63", bounds=b(53, 204, 179, 330)))
                + _node("android.widget.FrameLayout", "l65", clickable=True, bounds=b(205, 158, 792, 377),
                        children=_node("android.widget.LinearLayout", "ox6", bounds=b(205, 190, 792, 345), children=(
                            _node("android.widget.TextView", "l68", "demo_sender", bounds=b(205, 190, 370, 240))
                            + _node("android.widget.TextView", "l60", message, bounds=b(205, 245, 792, 345)))))
                + _node("android.widget.FrameLayout", "l6_", clickable=True, bounds=b(792, 158, 1059, 377),
                        children=_node("android.widget.TextView", "l5z", reply, bounds=b(824, 242, 1006, 292)))))))))


class _Device:
    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)
        self.swipes = []

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def get_screen_size(self):
        return 1080, 2400

    def swipe_coordinates(self, x1, y1, x2, y2, duration=0.5):
        self.swipes.append((x1, y1, x2, y2))


class _Logger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


def _popups(xml):
    actions = PopupActions.__new__(PopupActions)
    actions.device = _Device(xml)
    actions.logger = _Logger()
    actions.popup_selectors = POPUP_SELECTORS
    return actions


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)


@pytest.fixture
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


@pytest.fixture
def english():
    set_active_locale("en")
    yield
    set_active_locale(None)


@pytest.mark.parametrize("message", ["t'ont envoyé de nouveaux messages.", "a envoyé un sticker"])
def test_the_real_banner_is_found_and_swiped_from_its_middle(french, message):
    popups = _popups(_screen(_banner(message)))
    found = first_matching(popups.device, POPUP_SELECTORS.notification_banner)
    assert [el.attrib.get("resource-id") for el in found] == [ID + "l66"]

    assert popups.dismiss_notification_banner() is True
    assert popups.device.swipes == [((21 + 1059) // 2, (158 + 377) // 2, (21 + 1059) // 2, 0)]


def test_the_comment_sheet_is_not_a_banner(french):
    """Its rows carry clickable « Répondre » buttons: no banner, no swipe."""
    popups = _popups(SHEET_4703)
    assert first_matching(popups.device, POPUP_SELECTORS.notification_banner) == []
    assert popups.dismiss_notification_banner() is False
    assert popups.device.swipes == []


def test_a_banner_shape_away_from_the_top_is_left_alone(french):
    """The gesture is a swipe up from the banner: only a banner at the top earns it."""
    popups = _popups(_screen(_banner("a envoyé un sticker", shift=1200)))
    assert first_matching(popups.device, POPUP_SELECTORS.notification_banner)
    assert popups.dismiss_notification_banner() is False
    assert popups.device.swipes == []


def test_an_english_reply_button_is_not_a_banner(english):
    """The English entry was any clickable « Reply », which a comment row carries."""
    row = _node("android.widget.LinearLayout", clickable=True, bounds="[0,1400][1080,1560]", children=(
        _node("android.widget.TextView", "h2y", "Invented comment", bounds="[207,1382][546,1449]")
        + _node("android.widget.Button", "drx", "Reply", clickable=True, bounds="[352,1474][477,1530]")))
    popups = _popups(_screen(row))
    assert popups.dismiss_notification_banner() is False
    assert popups.device.swipes == []
