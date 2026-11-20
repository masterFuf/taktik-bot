"""`_find_and_click` asks all its selectors of ONE photo per turn and taps from that photo.

Step 5 of the one-photo spec, L4. `d.xpath()` took one dump per selector asked, and one more to
read the bounds of the element found (`.get()`): a back button found by the second of six
selectors cost three dumps, a miss six a turn. Unchanged: the order of the selectors, "the first
that finds", the timeout, the pause between turns, the human tap inside the element.

What changes on purpose: an element found without an area (bounds `[0,0][0,0]`) is not tapped.
Its centre click tapped the corner of the screen and answered True.

The screen is a real capture, anonymized: another profile, Instagram 410 in English.
"""

import time

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from unit.paths import CORE

PROFILE = (CORE / "tests/unit/social_media/instagram/fixtures/ig410_en_profile_following.xml").read_text(
    encoding="utf-8")
# Where the capture draws its back button (the second selector of `back_buttons` finds it).
BACK = (0, 77, 132, 231)


class _Phone:
    """uiautomator2 as the facade drives it: one screen, its dumps counted, its taps recorded."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2400}

    def __init__(self, screen):
        self.screen = screen
        self.dumps = 0
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        self.dumps += 1
        return self.screen

    def click(self, x, y):
        self.taps.append((x, y))

    def long_click(self, x, y, _duration=None):
        self.taps.append((x, y))

    def window_size(self):
        return 1080, 2400


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    monkeypatch.setattr(time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    return now


def _navigation(screen):
    phone = _Phone(screen)
    return NavigationActions(DeviceFacade(CloneAwareDeviceProxy(phone, "com.instagram.android"))), phone


def test_a_find_is_one_dump_and_the_tap_lands_inside_the_element():
    navigation, phone = _navigation(PROFILE)

    assert navigation._find_and_click(NAVIGATION_SELECTORS.back_buttons, timeout=1, human_delay=False) is True

    assert phone.dumps == 1
    (x, y), = phone.taps
    assert BACK[0] <= x <= BACK[2] and BACK[1] <= y <= BACK[3]


def test_a_miss_is_one_dump_a_turn():
    navigation, phone = _navigation(PROFILE)
    absent = [selector for selector in NAVIGATION_SELECTORS.back_buttons if "Retour" in selector]

    assert navigation._find_and_click(absent, timeout=1.2, human_delay=False, report_miss=False) is False

    # Turns at 0, 0.5 and 1.0 s: one photo each, whatever the number of selectors.
    assert phone.dumps == 3
    assert phone.taps == []


def test_an_element_without_an_area_is_not_tapped():
    flat = PROFILE.replace(f'bounds="[{BACK[0]},{BACK[1]}][{BACK[2]},{BACK[3]}]"', 'bounds="[0,0][0,0]"')
    assert flat != PROFILE
    navigation, phone = _navigation(flat)

    assert navigation._find_and_click(NAVIGATION_SELECTORS.back_buttons, timeout=1, human_delay=False) is False

    assert phone.taps == []
