"""The profile tab is the bottom bar's, and the own profile is given time to load.

Every workflow starts by opening the account's own profile (`initialize_session`). On a Pixel 3
(Instagram 410 in French) it often ended on the profile's Reels or Reposts tab. Two causes, both
read on the phone, six cold starts of Instagram:

- after the tap on the profile tab, the tab switches at once but the profile header comes 2.5 to
  4.7 s later (`fixtures/ig410_fr_own_profile_loading.xml`: the action bar and a spinner, no
  header). The check made about 1 s after the tap said "not a profile" and a second attempt
  began (3 cold starts out of 6);
- the second attempt looked for `contains(@resource-id, "profile_tab")`, which also names the
  grid tabs of a profile page (profile_tabs_container, profile_tab_layout,
  profile_tab_icon_view), earlier in the dump than the bottom bar. Once the profile had loaded,
  the tap went to the middle of that bar: Reels or Reposts (2 cold starts out of 6).

The screens are real dumps, anonymized: Instagram 410 in French and in English (home feed, own
profile, own professional profile, the Pixel 3 cold start: feed, loading profile, loaded profile),
447 in French on a Pixel 6a, and screens without the bottom bar (a profile opened from a search,
followers lists, a story). The phone below is uiautomator2's own xpath engine behind the facade
production mounts (`CloneAwareDeviceProxy`); a tap reaches the deepest clickable node under it.
"""

from pathlib import Path

import pytest
from loguru import logger
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS

IG = "com.instagram.android"
BOTTOM_PROFILE_TAB = f"{IG}:id/profile_tab"
FIXTURES = Path(__file__).parent / "fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


OWN_PROFILES = [
    "ig410_fr_own_profile.xml",
    "ig410_en_own_profile.xml",
    "ig410_fr_own_profile_professional.xml",
    "ig410_en_own_profile_professional.xml",
    "ig410_fr_own_profile_with_suggestions.xml",
    "ig410_fr_own_profile_after_cold_start.xml",
    "ig447_fr_own_profile_professional.xml",
]
WITH_TAB_BAR = OWN_PROFILES + [
    "ig410_fr_home_feed.xml",
    "ig410_fr_home_feed_before_profile_tap.xml",
    "ig410_fr_own_profile_loading.xml",
    "ig447_fr_home_feed_cold_start.xml",
]
# No bottom bar: grid tabs of another profile, avatars that say "Profile picture of ...", the
# tab bar of a hashtag page (search_tab_bar_layout).
WITHOUT_TAB_BAR = [
    "ig410_fr_profile_opened_from_search.xml",
    "ig410_fr_hashtag_page.xml",
    "ig447_fr_hashtag_page.xml",
    "ig410_fr_followers_list_top.xml",
    "ig410_en_followers_list.xml",
    "ig410_en_story_viewer.xml",
]
LANGS = [None, "fr", "en"]


@pytest.fixture
def locale():
    before = active_locale()
    yield set_active_locale
    set_active_locale(before)


def _designated(xml):
    """Per selector, in `_find_and_click`'s order, the nodes it names on this screen, through the
    same rewrite as production's `d.xpath()`."""
    tree = parse_ui_dump(xml.encode("utf-8"))
    proxy = CloneAwareDeviceProxy(object(), IG)
    return [tree.xpath(proxy.rewrite_xpath(selector)) for selector in NAVIGATION_SELECTORS.profile_tab]


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("screen", WITH_TAB_BAR)
def test_the_first_node_found_is_the_bottom_bar_profile_tab(locale, lang, screen):
    locale(lang)
    first = next(nodes[0] for nodes in _designated(_capture(screen)) if nodes)
    assert first.get("resource-id") == BOTTOM_PROFILE_TAB


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("screen", WITH_TAB_BAR)
def test_no_selector_names_the_grid_tabs_of_the_profile(locale, lang, screen):
    locale(lang)
    named = {node.get("resource-id") for nodes in _designated(_capture(screen)) for node in nodes}
    assert named == {BOTTOM_PROFILE_TAB}


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("screen", WITHOUT_TAB_BAR)
def test_without_the_bottom_bar_nothing_is_named(locale, lang, screen):
    locale(lang)
    named = [(node.get("resource-id"), node.get("content-desc"))
             for nodes in _designated(_capture(screen)) for node in nodes]
    assert named == []


# ── The production navigation on the Pixel 3 cold start ──────────────────────────────────────

HOME = _capture("ig410_fr_home_feed_before_profile_tap.xml")
LOADING = _capture("ig410_fr_own_profile_loading.xml")
OWN_PROFILE = _capture("ig410_fr_own_profile_after_cold_start.xml")
HEADER_DELAY_S = 3.0  # measured after the tap: 2.5, 2.6, 3.0 and 4.7 s


class _Clock:
    """Each reading of the time moves it on a little, each sleep by its length."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        self.now += 0.05
        return self.now

    def sleep(self, seconds=0.0, *_a, **_k):
        self.now += max(0.0, float(seconds))


class _Pixel3:
    """The feed after a cold start; a tap on the bottom profile tab shows the profile at once,
    its header `HEADER_DELAY_S` later."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2160}

    def __init__(self, clock, screen):
        self.clock = clock
        self.screen = screen
        self.header_at = None
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        if self.header_at is not None and self.clock.now >= self.header_at:
            self.screen, self.header_at = OWN_PROFILE, None
        return self.screen

    def app_current(self):
        return {"package": IG}

    def window_size(self):
        return 1080, 2160

    def _node_under(self, x, y):
        hit = None
        for node in parse_ui_dump(self.dump_hierarchy().encode("utf-8")).iter():
            bounds = node.get("bounds")
            if not bounds or node.get("clickable") != "true":
                continue
            left, top, right, bottom = map(int, bounds.replace("][", ",").strip("[]").split(","))
            if left <= x < right and top <= y < bottom:
                hit = node
        return hit

    def click(self, x, y):
        node = self._node_under(x, y)
        name = node.get("resource-id").split("/")[-1]
        self.taps.append(name if name != "profile_tab_icon_view" else node.get("content-desc"))
        if name == "profile_tab" and self.screen is HOME:
            self.screen, self.header_at = LOADING, self.clock.now + HEADER_DELAY_S

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def press(self, *_a, **_k):
        return True


@pytest.fixture
def pixel3(monkeypatch, locale):
    import time

    clock = _Clock()
    monkeypatch.setattr(time, "time", clock.time)
    monkeypatch.setattr(time, "monotonic", clock.time)
    monkeypatch.setattr(time, "sleep", clock.sleep)
    monkeypatch.setattr("taktik.core.shared.diagnostics.miss_capture.signaler_ecran_inconnu",
                        lambda *_a, **_k: None)
    locale("fr")

    def run(screen):
        phone = _Pixel3(clock, screen)
        nav = NavigationActions(DeviceFacade(CloneAwareDeviceProxy(phone, IG)))
        nav.logger = logger
        return nav.navigate_to_profile_tab(), phone

    return run


def test_from_the_cold_feed_one_tap_on_the_bottom_tab_and_the_grid_stays(pixel3):
    ok, phone = pixel3(HOME)
    assert ok
    assert phone.taps == ["profile_tab"]
    assert phone.screen is OWN_PROFILE


def test_on_the_loaded_own_profile_nothing_is_tapped(pixel3):
    ok, phone = pixel3(OWN_PROFILE)
    assert ok
    assert phone.taps == []
