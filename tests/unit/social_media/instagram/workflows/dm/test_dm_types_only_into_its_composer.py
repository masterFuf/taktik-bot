"""A DM is typed only into the composer of a conversation that is open, once the caret is in it.

Measured on a Pixel 6a (Instagram 447, French), 2026-10-25, a cold DM from a professional account to
an account that follows it: the profile's « Envoyer un message » was tapped, a new conversation
came up (header « Discussion professionnelle »), and the tap aimed at its composer opened Instagram's
help page (`help.instagram.com/...?ref=learn_more`) in Chrome 0.1 s later (the phone's logcat). The
66 characters were typed into nothing, then typed again; the run went on looking for a home tab in
Chrome. The opener had answered "Clicked Message button" without looking at what came up, and the
typing never asked whether the tap had put the caret in the composer.

The screens are real dumps of that phone, anonymized: the profile with its Message button, the new
conversation (keyboard down, the composer without the caret), the same conversation once a tap put
the caret in it, and the Chrome page that tap opened in the run. The phone is uiautomator2's own
xpath engine behind the clone proxy; what a tap opens is written in `doors`, per test.
"""

from types import SimpleNamespace

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.device.wait as wait_module
import taktik.core.social_media.instagram.workflows.dm.messaging as messaging
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.diagnostics import foreground_guard
from taktik.core.social_media.instagram.actions.atomic.text import dm_composer
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from taktik.core.social_media.instagram.workflows.dm.messaging import MessagingBusiness
from taktik.core.social_media.instagram.workflows.dm.reply_check import ReplyOutcome
from unit.paths import CORE

PKG = "com.instagram.android"
CHROME = "com.android.chrome"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
FILES = {
    "profile": "ig447_fr_profile_follows_us_message_button.xml",
    "conversation": "ig447_fr_dm_new_professional_conversation.xml",
    "conversation_focused": "ig447_fr_dm_new_professional_conversation_focused.xml",
    "chrome": "ig447_fr_chrome_help_page_from_conversation.xml",
}
SCREENS = {name: (FIXTURES / file).read_text(encoding="utf-8") for name, file in FILES.items()}
#: The elements a tap aims at, named by what the screen shows, not by the selector under test.
MESSAGE_BUTTON = '//*[@content-desc="Envoyer un message"]'
COMPOSER = '//*[@resource-id="com.instagram.android:id/row_thread_composer_edittext"]'
MESSAGE = "Test TAKTIK : premier message, conversation neuve."


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


class _Phone:
    wait_timeout = 0.0
    serial = "PHONE-1"

    def __init__(self, screen, doors):
        self.screen = screen
        self.doors = doors
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return SCREENS[self.screen]

    def app_current(self):
        return {"package": CHROME if self.screen == "chrome" else PKG}

    def window_size(self):
        return 1080, 2400

    def click(self, x, y):
        self.taps.append((self.screen, x, y))
        for (screen, xpath), opened in self.doors.items():
            if _inside((screen, x, y), screen, xpath):
                self.screen = opened
                return

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)


@pytest.fixture
def phone_on(monkeypatch):
    clock = SimpleNamespace(now=0.0)
    fake_time = SimpleNamespace(time=lambda: clock.now, monotonic=lambda: clock.now,
                                sleep=lambda s: setattr(clock, "now", clock.now + float(s or 0)))
    for module in (messaging, wait_module, dm_composer):
        monkeypatch.setattr(module, "time", fake_time)
    typed = []
    monkeypatch.setattr(dm_composer, "ensure_taktik_keyboard", lambda _device_id: True)
    # The keyboard: what reaches it is the test's answer; the field it fills is not under test.
    monkeypatch.setattr(dm_composer, "type_text_checked",
                        lambda _device, _device_id, text, **_k: typed.append(text) and False)
    foreground_guard.reinitialiser()

    def build(screen, doors):
        phone = _Phone(screen, doors)
        phone.typed = typed
        return MessagingBusiness(CloneAwareDeviceProxy(phone, PKG)), phone

    set_active_locale("fr")
    yield build
    set_active_locale(None)


def test_the_message_button_opens_the_conversation_and_says_so_once_it_is_up(phone_on):
    messaging_business, phone = phone_on("profile", {("profile", MESSAGE_BUTTON): "conversation"})

    assert messaging_business.open_conversation_from_profile("user_1") is True
    (tap,) = phone.taps
    assert _inside(tap, "profile", MESSAGE_BUTTON)


def test_a_message_button_tap_that_opens_no_conversation_is_not_an_open_conversation(phone_on):
    """The tap lands, nothing comes up (the profile stays): the opener says so."""
    messaging_business, phone = phone_on("profile", {})

    assert messaging_business.open_conversation_from_profile("user_1") is False
    (tap,) = phone.taps
    assert _inside(tap, "profile", MESSAGE_BUTTON)
    assert phone.typed == []


def test_a_composer_tap_that_opens_another_app_types_nothing(phone_on):
    """The run of 2026-10-25: the tap aimed at the composer brought Chrome up."""
    messaging_business, phone = phone_on("conversation", {("conversation", COMPOSER): "chrome"})

    assert messaging_business.send_in_open_conversation(MESSAGE, typos=False) is ReplyOutcome.NOT_SENT
    (tap,) = phone.taps
    assert _inside(tap, "conversation", COMPOSER)
    assert phone.typed == []
    assert phone.screen == "chrome"  # nothing more was tapped there


def test_a_composer_tap_that_leaves_the_caret_out_of_it_types_nothing(phone_on):
    """The tap lands and the screen stays as it was, the composer without the caret."""
    messaging_business, phone = phone_on("conversation", {})

    assert messaging_business.send_in_open_conversation(MESSAGE, typos=False) is ReplyOutcome.NOT_SENT
    assert len(phone.taps) == 1
    assert phone.typed == []


def test_once_the_caret_is_in_the_composer_the_message_goes_to_the_keyboard(phone_on):
    messaging_business, phone = phone_on("conversation", {("conversation", COMPOSER): "conversation_focused"})

    messaging_business.send_in_open_conversation(MESSAGE, typos=False)

    (tap,) = phone.taps
    assert _inside(tap, "conversation", COMPOSER)
    assert phone.typed == [MESSAGE]


def test_the_conversation_and_its_caret_are_read_by_the_catalogue():
    """The two readings the sending waits for, on the screens they name and on no other."""
    def shows(screen, xpath):
        return bool(etree.fromstring(SCREENS[screen].encode("utf-8")).xpath(xpath))

    assert [s for s in SCREENS if shows(s, DM_SELECTORS.conversation_screen_marker)] == [
        "conversation", "conversation_focused"]
    assert [s for s in SCREENS if shows(s, DM_SELECTORS.message_input_focused)] == ["conversation_focused"]
