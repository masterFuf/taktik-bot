"""`open_search` opens the general search, from the magnifier of the Home feed's header only.

Measured on a Pixel 3a (TikTok 43.1.4, the baseline) with the Lab's `tt.search.open` launched
from the inbox: the tap landed on the inbox's own magnifier, which searches the conversations.
The Home feed's id (`irz`) is absent there, and the French entry of the catalogue,
`//*[contains(@content-desc, "Rechercher")][@clickable="true"]`, took the first magnifier it
met. 46.6.3 and 46.9.3 have the same magnifier in their inbox.

The screens are real dumps, anonymized (every text and content-desc emptied except the app's
interface labels, the Android system bars removed): the 43.1.4 inbox and Home feed (Pixel 3a),
the 46.9.3 inbox and the 47.0.3 Home feed (Pixel 6a). The phone answers `xpath` through
uiautomator2's own engine; a tap on the Home tab of the inbox shows the Home feed, unless the
phone is told to obey nothing. Its clock jumps when the code waits.
"""

from pathlib import Path

import pytest
import uiautomator2.xpath as u2_xpath
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as shared_base_action
import taktik.core.shared.device.facade as shared_facade
from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.tiktok.actions.atomic.navigation.search_actions import SearchActions
from taktik.core.social_media.tiktok.actions.core.device_facade import DeviceFacade
from taktik.core.social_media.tiktok.services.navigation import reset
from taktik.core.social_media.tiktok.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import SEARCH_SELECTORS

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


INBOX_4314 = _read("tt4314_fr_inbox.xml")
HOME_4314 = _read("tt4314_fr_home.xml")
INBOX_4693 = _read("tt4693_fr_inbox.xml")
HOME_4703 = _read("tt4703_fr_home.xml")

# Bounds read on the dumps.
HOME_LOUPE_4314 = (926, 80, 1080, 234)
HOME_LOUPE_4703 = (933, 134, 1080, 281)
INBOX_LOUPE_4314 = (942, 77, 1063, 198)
INBOX_HOME_TAB_4314 = (0, 1953, 216, 2088)


def _inside(point, bounds):
    x, y = point
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


class _Clock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(0.0, seconds)

    def __getattr__(self, name):
        import time
        return getattr(time, name)


class _Phone:
    """uiautomator2 as these reads and taps touch it."""

    wait_timeout = 0.0

    def __init__(self, screen, obeys=True):
        self.screen = screen
        self.obeys = obeys
        self.xpath = XPathEntry(self)
        self.taps = []
        self.presses = []

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def window_size(self):
        return 1080, 2220

    def press(self, key, *_a):
        self.presses.append(key)

    def click(self, x, y):
        self.taps.append((x, y))
        if self.obeys and self.screen is INBOX_4314 and _inside((x, y), INBOX_HOME_TAB_4314):
            self.screen = HOME_4314

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    clock = _Clock()
    for module in (u2_xpath, shared_base_action, shared_facade, reset):
        monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    previous = active_locale()
    set_active_locale("fr")
    yield
    set_active_locale(previous)
    apply_version_overrides("tiktok", "43.1.4")


def _found(xml):
    """Bounds of every node the catalogue's magnifier selectors find on `xml`, as `d.xpath()`."""
    phone = _Phone(xml)
    found = []
    for selector in list(NAVIGATION_SELECTORS.search_button) + list(SEARCH_SELECTORS.search_icon):
        for element in phone.xpath(selector).all():
            if tuple(element.bounds) not in found:
                found.append(tuple(element.bounds))
    return found


# ── the selectors: the Home header's magnifier, and no other ─────────────────────────────────

@pytest.mark.parametrize("version, xml, loupe", [
    ("43.1.4", HOME_4314, HOME_LOUPE_4314),
    ("47.0.3", HOME_4703, HOME_LOUPE_4703),
], ids=["home-43.1.4", "home-47.0.3"])
def test_the_home_header_magnifier_is_still_found(version, xml, loupe):
    apply_version_overrides("tiktok", version)
    assert _found(xml) == [loupe]


@pytest.mark.parametrize("version, xml", [
    ("43.1.4", INBOX_4314),
    ("46.9.3", INBOX_4693),
], ids=["inbox-43.1.4", "inbox-46.9.3"])
def test_the_inbox_magnifier_is_not_the_search(version, xml):
    apply_version_overrides("tiktok", version)
    assert _found(xml) == []


# ── open_search: back to Home first, then the header's magnifier ─────────────────────────────

def test_from_the_inbox_it_goes_home_then_taps_the_header_magnifier():
    phone = _Phone(INBOX_4314)

    assert SearchActions(DeviceFacade(phone)).open_search() is True
    assert _inside(phone.taps[0], INBOX_HOME_TAB_4314)
    assert _inside(phone.taps[-1], HOME_LOUPE_4314)
    assert len(phone.taps) == 2


def test_on_the_home_feed_it_taps_the_header_magnifier_once():
    phone = _Phone(HOME_4314)

    assert SearchActions(DeviceFacade(phone)).open_search() is True
    assert len(phone.taps) == 1 and _inside(phone.taps[0], HOME_LOUPE_4314)


def test_when_home_cannot_be_reached_it_refuses_without_touching_the_inbox_magnifier():
    phone = _Phone(INBOX_4314, obeys=False)

    assert SearchActions(DeviceFacade(phone)).open_search() is False
    assert not any(_inside(tap, INBOX_LOUPE_4314) for tap in phone.taps)
    assert all(_inside(tap, INBOX_HOME_TAB_4314) for tap in phone.taps)
