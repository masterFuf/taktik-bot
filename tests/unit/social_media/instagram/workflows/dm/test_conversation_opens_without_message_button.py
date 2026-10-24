"""A profile without a Message button still opens its conversation, through its Options sheet.

Measured on a Pixel 6 Pro (Instagram 410, Android 17, in French), 2026-10-24: the welcome DM to a
new follower failed with "Could not find Message button on profile". That follower, private and not
followed back, shows no Message button in the profile header, only "Suivre en retour": the normal
case of a welcome DM. The profile's Options button opens a sheet whose last row is "Envoyer un
message". The cold DM opens its conversations by the same opener.

The screens are real dumps, anonymized: that profile and its Options sheet (the Pixel 6 Pro), and an
English profile with its Message button (existing fixture). The phone answers `xpath` from the screen
on show; a tap on the Options button opens the sheet; every tap is recorded.
"""

from types import SimpleNamespace

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.instagram.workflows.dm.messaging as messaging
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS
from taktik.core.social_media.instagram.workflows.dm.messaging import MessagingBusiness
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
SCREENS = {
    "profile_no_message_fr": (FIXTURES / "ig410_fr_profile_private_follow_back_no_message.xml").read_text(
        encoding="utf-8"
    ),
    "options_sheet_fr": (FIXTURES / "ig410_fr_profile_options_sheet.xml").read_text(encoding="utf-8"),
    "profile_with_message_en": (FIXTURES / "ig410_en_profile_with_message_button.xml").read_text(
        encoding="utf-8"
    ),
}
#: What a tap opens: (screen, xpath of the element tapped) -> the screen it brings up.
DOORS = {("profile_no_message_fr", PROFILE_SELECTORS.header_options_button): "options_sheet_fr"}


def _bounds(screen, xpath):
    node = etree.fromstring(SCREENS[screen].encode("utf-8")).xpath(xpath)[0]  # the one u2 taps
    left_top, right_bottom = node.get("bounds")[1:-1].split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


class _Phone:
    wait_timeout = 0.0

    def __init__(self, screen):
        self.screen = screen
        self.taps = []
        self.keys = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return SCREENS[self.screen]

    def app_current(self):
        return {"package": PKG}

    def window_size(self):
        return 1440, 3120

    def click(self, x, y):
        self.taps.append((self.screen, x, y))
        for (screen, xpath), opened in DOORS.items():
            left, top, right, bottom = _bounds(screen, xpath) if screen == self.screen else (0, 0, -1, -1)
            if left <= x <= right and top <= y <= bottom:
                self.screen = opened
                return

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def press(self, key, *_a):
        self.keys.append(key)


def _tapped_in(tap, screen, xpath):
    tapped_screen, x, y = tap
    left, top, right, bottom = _bounds(screen, xpath)
    return tapped_screen == screen and left <= x <= right and top <= y <= bottom


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch):
    monkeypatch.setattr(messaging, "time", SimpleNamespace(sleep=lambda *_: None))
    yield
    set_active_locale(None)


def test_a_profile_without_message_button_opens_the_conversation_from_its_options_sheet():
    set_active_locale("fr")
    phone = _Phone("profile_no_message_fr")

    assert MessagingBusiness(CloneAwareDeviceProxy(phone, PKG)).open_conversation_from_profile() is True

    (options, row) = phone.taps
    assert _tapped_in(options, "profile_no_message_fr", PROFILE_SELECTORS.header_options_button)
    (row_xpath,) = [x for x in PROFILE_SELECTORS.options_sheet_message_row if "Envoyer un message" in x]
    assert _tapped_in(row, "options_sheet_fr", row_xpath)


def test_a_profile_with_its_message_button_is_opened_by_the_button_alone():
    set_active_locale("en")
    phone = _Phone("profile_with_message_en")

    assert MessagingBusiness(CloneAwareDeviceProxy(phone, PKG)).open_conversation_from_profile() is True

    (tap,) = phone.taps
    button_xpath = PROFILE_SELECTORS.header_message_button[0]
    assert _tapped_in(tap, "profile_with_message_en", button_xpath)
