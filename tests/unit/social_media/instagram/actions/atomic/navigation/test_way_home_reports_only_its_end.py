"""The way home looks for the home tab after each Back without a warning nor a screen kept.

Measured on a Pixel 6a (Instagram 447, French), 2026-10-25, after a cold DM that went through:
from the conversation, the way home (`navigate_to_home`) looked for the home tab, missed it, pressed
Back, looked again... Each look that missed logged "No element found after 3s" as a warning and kept
a capture of the screen: four per DM, while a screen without the tab bar is exactly what the way
expects until it gets home. Only a way that ends without home is worth a warning and a capture.

The screens are real dumps of that phone, anonymized, in the order a Back leaves them after a cold
DM: the conversation with the keyboard up, the same without it, the profile opened from the search,
the search results, and the home feed. The phone is uiautomator2's own xpath engine behind the
facade production mounts; a Back shows the next screen.
"""

import pytest
from loguru import logger
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from unit.paths import CORE

IG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
WAY_BACK = [
    "ig447_fr_dm_new_professional_conversation_focused.xml",
    "ig447_fr_dm_new_professional_conversation.xml",
    "ig447_fr_profile_follows_us_message_button.xml",
    "ig447_fr_search_results_account.xml",
    "ig447_fr_home_feed.xml",
]
SCREENS = [(FIXTURES / name).read_text(encoding="utf-8") for name in WAY_BACK]


class _Clock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        self.now += 0.05
        return self.now

    def sleep(self, seconds=0.0, *_a, **_k):
        self.now += max(0.0, float(seconds))


class _Phone:
    """A Back shows the next screen of `WAY_BACK`, up to `last` (the screen a Back no longer leaves)."""

    wait_timeout = 1.0

    def __init__(self, last):
        self.index = 0
        self.last = last
        self.backs = 0
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return SCREENS[self.index]

    def app_current(self):
        return {"package": IG}

    def window_size(self):
        return 1080, 2400

    def press(self, key, *_a, **_k):
        if key == "back":
            self.backs += 1
            self.index = min(self.index + 1, self.last)
        return True

    def click(self, x, y):
        self.taps.append((x, y))

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)


@pytest.fixture
def way_home(monkeypatch):
    import time

    clock = _Clock()
    monkeypatch.setattr(time, "time", clock.time)
    monkeypatch.setattr(time, "monotonic", clock.time)
    monkeypatch.setattr(time, "sleep", clock.sleep)
    kept = []
    monkeypatch.setattr("taktik.core.shared.diagnostics.miss_capture.signaler_ecran_inconnu",
                        lambda *_a, **_k: kept.append(1))
    warnings = []
    sink = logger.add(lambda message: warnings.append(message.record["message"]), level="WARNING")
    set_active_locale("fr")

    def run(last):
        phone = _Phone(last)
        nav = NavigationActions(DeviceFacade(CloneAwareDeviceProxy(phone, IG)))
        nav.logger = logger
        return nav.navigate_to_home(), phone, warnings, kept

    yield run
    logger.remove(sink)
    set_active_locale(None)


def test_a_way_home_that_arrives_says_nothing_and_keeps_no_screen(way_home):
    arrived, phone, warnings, kept = way_home(last=len(SCREENS) - 1)

    assert arrived is True
    assert phone.backs == 4  # the keyboard, the conversation, the profile, the search results
    assert warnings == [] and kept == []


def test_a_way_home_that_ends_without_home_says_so_once_with_its_screen(way_home):
    arrived, phone, warnings, kept = way_home(last=len(SCREENS) - 2)  # the search results, at most

    assert arrived is False
    assert phone.backs == 4
    assert [w for w in warnings if "No element found" in w] == ["🚫 No element found after 3s"]
    assert kept == [1]
