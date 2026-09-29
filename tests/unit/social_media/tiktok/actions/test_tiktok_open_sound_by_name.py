"""`open_sound_by_name` searches through the production navigation.

Its lazy import aimed at `actions/navigation/navigation_actions`, which does not exist (the
navigation lives under `actions/atomic/navigation/`): the method raised at its first line. It has no
caller today; the gate `import-resolves` found it with the four others.

The screen is a real capture: the Home feed of TikTok 43.1.4 in French (Pixel 3a), anonymized, read by
uiautomator2's own engine. The phone does not move: the magnifier is tapped, the search field never
comes, and the method says so and returns "" (no sound opened), as it does on a phone.
"""

import pytest
import uiautomator2.xpath as u2_xpath
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as shared_base_action
import taktik.core.shared.device.facade as shared_facade
import taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions as sound_module
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions import SoundActions
from taktik.core.social_media.tiktok.services.navigation import reset
from taktik.core.social_media.tiktok.ui.selectors.locales import active_locale, set_active_locale
from unit.paths import CORE

HOME = (CORE / "tests/unit/social_media/tiktok/fixtures/tt4314_fr_home.xml").read_text(encoding="utf-8")
# The Home feed's magnifier, bounds read on the capture (as in test_search_opens_from_the_home_header).
HOME_LOUPE = (926, 80, 1080, 234)


class _Clock:
    """Time moves only when the code waits."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    monotonic = perf_counter = time

    def sleep(self, seconds):
        self.now += max(0.0, seconds)


class _Phone:
    """Shows the capture, records the taps; the xpath queries are uiautomator2's."""

    wait_timeout = 0.0

    def __init__(self, screen):
        self.screen = screen
        self.xpath = XPathEntry(self)
        self.taps = []

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def window_size(self):
        return 1080, 2220

    def click(self, x, y):
        self.taps.append((x, y))


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    clock = _Clock()
    for module in (u2_xpath, shared_base_action, shared_facade, reset, sound_module):
        monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    previous = active_locale()
    set_active_locale("fr")
    yield
    set_active_locale(previous)


def test_open_sound_by_name_opens_the_search_from_the_home_feed():
    phone = _Phone(HOME)

    assert SoundActions(phone).open_sound_by_name("Umbrella") == ""

    left, top, right, bottom = HOME_LOUPE
    assert len(phone.taps) == 1
    x, y = phone.taps[0]
    assert left <= x <= right and top <= y <= bottom
