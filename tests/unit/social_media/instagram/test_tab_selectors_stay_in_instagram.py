"""The home and search tabs are Instagram's, never the launcher's; going home from outside
Instagram opens it.

The Lab's `navigation.go_home` failed in 14 s on a Pixel 3: the previous run had closed
Instagram, and the phone showed the Android launcher. The French home-tab fallback,
`contains(@content-desc,"Accueil") and not(systemui)`, matched the Pixel launcher's full-screen
`accessibility_action_view` (content-desc "Accueil"): four taps at random points of the home
screen, then Backs that a launcher ignores. The search-tab fallback matched the launcher's
Google search bar the same way (a Lab `navigation.go_search` once ended in the Google app).

Both fallbacks now look inside Instagram's tab bar, where every real home and search tab of
the corpus sits, and `navigate_to_home` opens Instagram when it is not in the foreground.

Instagram in French names its home tab "Home", in English, beside "Reels", "Rechercher et
explorer" and "Profil": every French dump of the corpus (410 and 447, four phones), and a cold
start of 447 on a Pixel 6a (Android and Instagram in French, Instagram force-stopped then opened
from the launcher), so not a leftover of a language switch. The French entries look for "Home".

The screens are real dumps, anonymized: the Pixel launcher (Android 12, French), and Instagram
410 in French on a Pixel 3 (home feed, own profile, a followers list, the account results of a
search) and on a Pixel 3a (the likers sheet of a post, a home feed whose home tab is the selected
node), 447 in French on a Pixel 6a (the home feed after the cold start), and in English on another
phone (the story camera). No phone holds an English Android:
the English runs read the French launcher. The phone is uiautomator2's own xpath engine behind the
facade production mounts (`CloneAwareDeviceProxy`); a tap reaches the clickable node under it.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from loguru import logger
from lxml import etree
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.actions import base_action as shared_base_action
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS
from unit.paths import CORE

IG = "com.instagram.android"
LAUNCHER_PKG = "com.google.android.apps.nexuslauncher"
FIXTURES = Path(__file__).parent / "fixtures"


def _capture(path):
    return path.read_text(encoding="utf-8")


LAUNCHER = _capture(CORE / "tests/unit/shared/device/fixtures/android12_fr_launcher_home.xml")
FEED = _capture(FIXTURES / "ig410_fr_home_feed_tab_icon_selected.xml")
FEED_HOME_TAB_SELECTED = _capture(FIXTURES / "ig410_fr_home_feed_reel_row.xml")
FEED_447_COLD_START = _capture(FIXTURES / "ig447_fr_home_feed_cold_start.xml")
OWN_PROFILE = _capture(FIXTURES / "ig410_fr_own_profile.xml")
# Instagram 410 shows a followers list without the tab bar.
FOLLOWERS = _capture(FIXTURES / "ig410_fr_followers_list_top.xml")

# Instagram's own nodes that hold the words without being a tab: the story camera's "Back to Home"
# button, the search field of the search results, and the likers sheet of a post, whose search
# glyph and field say "Rechercher" above a tab bar (Pixel 3a, 410 in French, June).
CAMERA = _capture(FIXTURES / "ig410_en_story_camera.xml")
SEARCH_RESULTS = _capture(FIXTURES / "ig410_fr_account_search_results.xml")
LIKERS_SHEET = _capture(FIXTURES / "ig410_fr_likers_sheet.xml")


def _matches(xml, selectors):
    tree = etree.fromstring(xml.encode("utf-8"))
    return [node.get("resource-id") or node.get("content-desc")
            for selector in selectors for node in tree.xpath(selector)]


def _tabs_without_their_ids(xml):
    """The same tab bar, its tabs stripped of the ids the base selectors know."""
    tree = etree.fromstring(xml.encode("utf-8"))
    for tab in tree.xpath(f'//*[@resource-id="{IG}:id/tab_bar"]/*'):
        tab.set("resource-id", "")
    return etree.tostring(tree, encoding="unicode")


@pytest.fixture
def locale():
    before = active_locale()
    yield set_active_locale
    set_active_locale(before)


@pytest.mark.parametrize("lang", [None, "fr", "en"])
def test_no_home_or_search_tab_on_the_launcher(locale, lang):
    locale(lang)
    assert _matches(LAUNCHER, NAVIGATION_SELECTORS.home_tab) == []
    assert _matches(LAUNCHER, NAVIGATION_SELECTORS.search_tab) == []
    assert _matches(LAUNCHER, [FEED_SCROLL_SELECTORS.home_tab_xpath]) == []
    assert _matches(LAUNCHER, DETECTION_SELECTORS.home_screen_indicators) == []


@pytest.mark.parametrize("screen", [CAMERA, SEARCH_RESULTS], ids=["camera", "search_results"])
@pytest.mark.parametrize("lang", [None, "fr", "en"])
def test_the_words_outside_the_tab_bar_are_not_tabs(locale, lang, screen):
    locale(lang)
    assert _matches(screen, NAVIGATION_SELECTORS.home_tab) == []
    assert _matches(screen, NAVIGATION_SELECTORS.search_tab) == []


@pytest.mark.parametrize("lang", [None, "fr", "en"])
def test_a_search_field_above_the_tab_bar_is_not_the_search_tab(locale, lang):
    locale(lang)
    assert set(_matches(LIKERS_SHEET, NAVIGATION_SELECTORS.search_tab)) == {f"{IG}:id/search_tab"}


@pytest.mark.parametrize("lang", [None, "fr", "en"])
def test_the_tabs_of_the_tab_bar_are_still_found(locale, lang):
    locale(lang)
    assert f"{IG}:id/feed_tab" in _matches(FEED, NAVIGATION_SELECTORS.home_tab)
    assert f"{IG}:id/search_tab" in _matches(FEED, NAVIGATION_SELECTORS.search_tab)


def test_the_localized_fallback_finds_a_tab_without_its_id(locale):
    """What the fallback is for: a tab-bar tab whose id the base selector does not know."""
    bar = _tabs_without_their_ids(FEED)
    locale("en")
    assert _matches(bar, NAVIGATION_SELECTORS.home_tab) == ["Home"]
    locale("fr")
    assert _matches(bar, NAVIGATION_SELECTORS.search_tab) == ["Rechercher et explorer"]


@pytest.mark.parametrize("screen", [FEED, FEED_447_COLD_START], ids=["410", "447-cold-start"])
def test_the_french_fallback_finds_the_home_tab_of_a_french_tab_bar(locale, screen):
    locale("fr")
    assert _matches(_tabs_without_their_ids(screen), NAVIGATION_SELECTORS.home_tab) == ["Home"]


def test_the_french_home_screen_fallback_reads_the_selected_home_tab(locale):
    """The home screen told by its selected home tab once the tab ids moved; the own profile,
    whose home tab is in the same bar but not selected, is not the home screen."""
    locale("fr")
    home = _tabs_without_their_ids(FEED_HOME_TAB_SELECTED)
    assert _matches(home, DETECTION_SELECTORS.home_screen_indicators) == ["Home"]
    assert _matches(_tabs_without_their_ids(OWN_PROFILE), DETECTION_SELECTORS.home_screen_indicators) == []


class _Phone:
    """The launcher or Instagram: Back pops one Instagram screen, a tap on the home tab shows the
    feed, `app_start` opens Instagram on its feed."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2160}
    BACK = {FOLLOWERS: OWN_PROFILE, OWN_PROFILE: FEED}

    def __init__(self, screen):
        self.screen = screen
        self.taps = []
        self.started = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def window_size(self):
        return 1080, 2160

    def app_current(self):
        return {"package": LAUNCHER_PKG if self.screen == LAUNCHER else IG}

    def app_start(self, package, *_a, **_k):
        self.started.append(package)
        self.screen = FEED

    def press(self, key):
        if key == "back":
            self.screen = self.BACK.get(self.screen, self.screen)

    def _tapped(self, x, y):
        """The clickable node under the finger, the deepest one: the node Android hands the tap to."""
        hit = None
        for node in etree.fromstring(self.screen.encode("utf-8")).iter("node"):
            left, top, right, bottom = map(int, node.get("bounds").replace("][", ",").strip("[]").split(","))
            if left <= x < right and top <= y < bottom and node.get("clickable") == "true":
                hit = node
        return hit

    def click(self, x, y):
        node = self._tapped(x, y)
        self.taps.append((node.get("package"), node.get("resource-id") or node.get("content-desc")))
        if node.get("resource-id") == f"{IG}:id/feed_tab":
            self.screen = FEED

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)


@pytest.fixture
def no_wait(monkeypatch):
    clock = SimpleNamespace(now=0.0)

    def _sleep(seconds=0.0, *_a, **_k):
        clock.now += seconds

    import time

    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(shared_base_action, "time", SimpleNamespace(time=lambda: clock.now, sleep=_sleep))
    monkeypatch.setattr("taktik.core.shared.diagnostics.miss_capture.signaler_ecran_inconnu",
                        lambda *_a, **_k: None)


def _go_home(screen):
    phone = _Phone(screen)
    nav = NavigationActions(DeviceFacade(CloneAwareDeviceProxy(phone, IG)))
    nav.logger = logger
    return nav.navigate_to_home(), phone


def test_from_the_launcher_it_opens_instagram_and_never_taps_the_launcher(no_wait, locale):
    locale(None)  # tonight's case: the app was not in the foreground, the language unknown
    ok, phone = _go_home(LAUNCHER)
    assert ok
    assert phone.started == [IG]
    assert not [tap for tap in phone.taps if tap[0] != IG]
    assert phone.screen == FEED


def test_from_a_followers_list_it_backs_out_then_taps_home(no_wait, locale):
    locale("fr")
    ok, phone = _go_home(FOLLOWERS)
    assert ok
    assert phone.started == []
    assert phone.taps == [(IG, f"{IG}:id/feed_tab")]
    assert phone.screen == FEED


# A hashtag page hides the bottom bar and has a tab bar of its own, `search_tab_bar_layout` (For
# you, Accounts, Not personalized, Audio), whose id begins like the search tab's. The search tab's
# `contains(@resource-id, "...:id/search_tab")` named it first on the 9 hashtag pages of the
# corpus and the captures (410 in French and in English, 447 in French): a tap in its middle opened
# one of its tabs.
HASHTAG_PAGES = ["ig410_fr_hashtag_page.xml", "ig410_en_hashtag_page.xml", "ig447_fr_hashtag_page.xml"]


@pytest.mark.parametrize("name", HASHTAG_PAGES)
@pytest.mark.parametrize("lang", [None, "fr", "en"])
def test_the_tab_bar_of_a_hashtag_page_is_not_the_search_tab(locale, lang, name):
    locale(lang)
    assert _matches(_capture(FIXTURES / name), NAVIGATION_SELECTORS.search_tab) == []


@pytest.mark.parametrize("name", HASHTAG_PAGES)
def test_on_a_hashtag_page_the_search_tab_is_not_tapped(no_wait, locale, name):
    locale("fr")
    phone = _Phone(_capture(FIXTURES / name))
    nav = NavigationActions(DeviceFacade(CloneAwareDeviceProxy(phone, IG)))
    nav.logger = logger
    assert nav._find_and_click(NAVIGATION_SELECTORS.search_tab, timeout=3) is False
    assert phone.taps == []
