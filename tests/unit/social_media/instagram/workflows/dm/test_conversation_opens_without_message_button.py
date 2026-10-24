"""A profile without a Message button still opens its conversation, from the inbox's new message.

Measured on 2026-10-24: an account that follows us and that we do not follow back shows no Message
button in its profile header, only "Suivre en retour", public or private, on a Pixel 6 Pro
(Instagram 410) and a Pixel 6a (447). The welcome DM to a new follower, whose normal case it is,
failed with "Could not find Message button on profile"; the cold DM ended "no_conversation". The
profile's Options sheet offers "Envoyer un message" in 410 only; the inbox's "Nouveau message"
picker works in both: the handle typed in its "À :" field, the row of exactly that handle tapped
(never the invitation row above it, whose "Inviter" button would invite someone).

The screens are real dumps, anonymized, of the Pixel 6a (447, French): that profile, the inbox,
the picker before and after the handle was typed, the home feed (existing fixture); and the
Pixel 6 Pro's private follower (410). The phone is uiautomator2's own xpath engine behind the
clone proxy; a tap on the Direct tab opens the inbox, on "Nouveau message" the picker. Three seams,
each covered by its own tests: the way home (`navigate_to_home`), the keyboard switch, and the
typing, which here shows the picker's results. What a tap on the row opens has no capture yet.
"""

import re
from types import SimpleNamespace

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.device.wait as wait_module
import taktik.core.social_media.instagram.workflows.dm.messaging as messaging
import taktik.core.social_media.instagram.workflows.dm.navigation as navigation
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from taktik.core.social_media.instagram.workflows.dm.messaging import MessagingBusiness
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
FILES = {
    "profile": "ig447_fr_profile_follows_us_no_message.xml",
    "home": "ig447_fr_home_feed.xml",
    "inbox": "ig447_fr_dm_inbox_pills.xml",
    "picker": "ig447_fr_dm_new_message_picker.xml",
    "results": "ig447_fr_dm_new_message_results.xml",
    "private_410": "ig410_fr_profile_private_follow_back_no_message.xml",
    "own_profile": "ig410_fr_own_profile.xml",
}
SCREENS = {name: (FIXTURES / file).read_text(encoding="utf-8") for name, file in FILES.items()}
HANDLE = "user_1"  # the account of the 447 profile, as the anonymiser named it in every screen
#: The two rows of the results, named by what they show, not by the selector under test.
ACCOUNT_ROW = (f'//*[@resource-id="com.instagram.android:id/row_user_primary_name"][@text="{HANDLE}"]'
               '/ancestor::*[@resource-id="com.instagram.android:id/user_row_background"][1]')
INVITATION_ROW = ('//*[@resource-id="com.instagram.android:id/row_direct_action_button"]'
                  '/ancestor::*[@resource-id="com.instagram.android:id/user_row_background"][1]')
#: What a tap opens: (screen, xpath of the element tapped) -> the screen it brings up.
DOORS = {
    ("home", '//*[@resource-id="com.instagram.android:id/direct_tab"]'): "inbox",
    ("inbox", '//*[@content-desc="Nouveau message"]'): "picker",
}


def _bounds(screen, xpath):
    node = etree.fromstring(SCREENS[screen].encode("utf-8")).xpath(xpath)[0]
    left_top, right_bottom = node.get("bounds")[1:-1].split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


def _inside(tap, screen, xpath):
    tapped_screen, x, y = tap
    left, top, right, bottom = _bounds(screen, xpath)
    return tapped_screen == screen and left <= x <= right and top <= y <= bottom


_UI_SELECTOR = {
    "description": lambda node, value: node.get("content-desc") == value,
    "descriptionContains": lambda node, value: value in (node.get("content-desc") or ""),
    "resourceId": lambda node, value: node.get("resource-id") == value,
    "resourceIdMatches": lambda node, value: re.fullmatch(value, node.get("resource-id") or "") is not None,
}


class _Selection:
    """`d(...)` as far as the inbox opener asks it: `exists`, and the bounds a tap reads."""

    def __init__(self, nodes):
        self._nodes = nodes

    @property
    def exists(self):
        return bool(self._nodes)

    @property
    def info(self):
        left_top, right_bottom = self._nodes[0].get("bounds")[1:-1].split("][")
        left, top = (int(v) for v in left_top.split(","))
        right, bottom = (int(v) for v in right_bottom.split(","))
        return {"bounds": {"left": left, "top": top, "right": right, "bottom": bottom}}


class _Phone:
    wait_timeout = 0.0
    serial = "PHONE-1"

    def __init__(self, screen):
        self.screen = screen
        self.taps = []
        self.typed = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return SCREENS[self.screen]

    def app_current(self):
        return {"package": PKG}

    def window_size(self):
        return 1080, 2400

    def __call__(self, **selector):
        nodes = etree.fromstring(SCREENS[self.screen].encode("utf-8")).iter("node")
        return _Selection([n for n in nodes if all(_UI_SELECTOR[k](n, v) for k, v in selector.items())])

    def click(self, x, y):
        self.taps.append((self.screen, x, y))
        for (screen, xpath), opened in DOORS.items():
            if screen == self.screen and _inside((screen, x, y), screen, xpath):
                self.screen = opened
                return

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def press(self, *_a):
        pass


@pytest.fixture
def phone_on(monkeypatch):
    clock = SimpleNamespace(now=0.0)
    fake_time = SimpleNamespace(time=lambda: clock.now,
                                sleep=lambda s: setattr(clock, "now", clock.now + float(s or 0)))
    for module in (messaging, navigation, wait_module):
        monkeypatch.setattr(module, "time", fake_time)

    def build(screen):
        phone = _Phone(screen)

        def home(_self):
            phone.screen = "home"
            return True

        def typed(_self, text, **_kwargs):
            phone.typed.append(text)
            phone.screen = "results"
            return True

        monkeypatch.setattr(NavigationActions, "navigate_to_home", home)
        monkeypatch.setattr(MessagingBusiness, "_ensure_taktik_keyboard", lambda _self: True)
        monkeypatch.setattr(MessagingBusiness, "_clear_text_with_taktik_keyboard", lambda _self: True)
        monkeypatch.setattr(MessagingBusiness, "_type_text_checked", typed)
        return phone

    set_active_locale("fr")
    yield build
    set_active_locale(None)


def test_a_profile_without_message_button_writes_from_the_new_message_picker(phone_on):
    phone = phone_on("profile")

    opened = MessagingBusiness(CloneAwareDeviceProxy(phone, PKG)).open_conversation_from_profile(f"@{HANDLE}")

    assert opened is True
    assert phone.typed == [HANDLE]
    direct_tab, new_message, field, row = phone.taps
    assert _inside(direct_tab, "home", '//*[@resource-id="com.instagram.android:id/direct_tab"]')
    assert _inside(new_message, "inbox", '//*[@content-desc="Nouveau message"]')
    assert _inside(field, "picker", DM_SELECTORS.new_message_search_field)
    assert _inside(row, "results", ACCOUNT_ROW)
    assert not _inside(row, "results", INVITATION_ROW)


def test_the_410_private_follower_takes_the_same_way(phone_on):
    phone = phone_on("private_410")

    assert MessagingBusiness(CloneAwareDeviceProxy(phone, PKG)).open_conversation_from_profile(HANDLE) is True
    assert phone.typed == [HANDLE]


def test_without_a_handle_nothing_is_tapped(phone_on):
    phone = phone_on("profile")

    assert MessagingBusiness(CloneAwareDeviceProxy(phone, PKG)).open_conversation_from_profile(None) is False
    assert phone.taps == []


def test_on_our_own_profile_the_inbox_is_not_tried(phone_on):
    phone = phone_on("own_profile")

    assert MessagingBusiness(CloneAwareDeviceProxy(phone, PKG)).open_conversation_from_profile(HANDLE) is False
    assert phone.taps == []
