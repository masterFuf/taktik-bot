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

The phone is uiautomator2's own xpath engine behind the facade production mounts
(`CloneAwareDeviceProxy`); the screens keep the ids and labels of real captures, names are
invented.
"""

from types import SimpleNamespace

import pytest
from loguru import logger
from lxml import etree
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.actions import base_action as shared_base_action
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS

IG = "com.instagram.android"
LAUNCHER_PKG = "com.google.android.apps.nexuslauncher"
UI = "com.android.systemui"


def _node(pkg, rid="", desc="", text="", bounds="[0,0][1,1]", selected="false", cls="android.view.View",
          children=""):
    rid = f"{pkg}:id/{rid}" if rid else ""
    return (f'<node index="0" text="{text}" resource-id="{rid}" class="{cls}" package="{pkg}" '
            f'content-desc="{desc}" clickable="true" enabled="true" selected="{selected}" '
            f'bounds="{bounds}">{children}</node>')


def _nav_bar():
    return _node(UI, bounds="[0,2028][1080,2160]", cls="android.widget.FrameLayout", children=(
        _node(UI, "back", desc="Retour", bounds="[129,2028][349,2160]")
        + _node(UI, "home_button", desc="Accueil", bounds="[430,2028][650,2160]")))


def _screen(*nodes):
    return '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">' + "".join(nodes) + "</hierarchy>"


def _tab_bar(selected):
    tabs = (("feed_tab", "Home", "[0,1907][216,2028]"),
            ("search_tab", "Rechercher et explorer", "[648,1907][864,2028]"),
            ("profile_tab", "Profil", "[864,1907][1080,2028]"))
    return _node(IG, "tab_bar", bounds="[0,1907][1080,2028]", cls="android.widget.LinearLayout", children="".join(
        _node(IG, rid, desc=desc, bounds=bounds, selected=str(rid == selected).lower(),
              cls="android.widget.FrameLayout")
        for rid, desc, bounds in tabs))


def _instagram(*nodes):
    return _screen(_node(IG, bounds="[0,0][1080,2028]", cls="android.widget.FrameLayout",
                         children="".join(nodes)), _nav_bar())


LAUNCHER = _screen(
    _node(LAUNCHER_PKG, bounds="[0,0][1080,2160]", cls="android.widget.FrameLayout", children=(
        _node(LAUNCHER_PKG, "accessibility_action_view", desc="Accueil", bounds="[0,77][1080,2028]")
        + _node(LAUNCHER_PKG, desc="Rechercher", bounds="[44,1812][1036,1944]"))),
    _nav_bar())

FEED = _instagram(_node(IG, "row_feed_photo_profile_name", text="someone.else", bounds="[134,236][958,306]"),
                  _tab_bar("feed_tab"))

OWN_PROFILE = _instagram(_node(IG, "action_bar_title", text="demo.account", bounds="[176,77][646,231]"),
                         _node(IG, "profile_header_container", bounds="[0,231][1080,1659]"),
                         _tab_bar("profile_tab"))

# Instagram 410 shows its own followers list without the tab bar.
OWN_FOLLOWERS = _instagram(
    _node(IG, "unified_follow_list_tab_layout", bounds="[0,231][1080,340]", children="".join(
        _node(IG, text=label, bounds=f"[{i * 360},231][{i * 360 + 360},340]")
        for i, label in enumerate(("Tous les followers", "À vérifier", "Comptes désactivés")))),
    _node(IG, "follow_list_username", text="friend.one", bounds="[200,600][700,650]"))

# Instagram's own nodes that hold the words without being a tab.
CAMERA_AND_CAROUSEL = _instagram(
    _node(IG, "camera_home_button", desc="Back to Home", bounds="[20,90][140,210]", cls="android.widget.Button"),
    _node(IG, "suggested_user_card_follow_button", desc="Suivre Demo | Home &amp; Office",
          bounds="[100,900][500,980]", cls="android.widget.Button"),
    _node(IG, "search_edit_text", desc="Rechercher", bounds="[100,240][980,330]"))


def _matches(xml, selectors):
    tree = etree.fromstring(xml.encode("utf-8"))
    return [node.get("resource-id") or node.get("content-desc")
            for selector in selectors for node in tree.xpath(selector)]


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


@pytest.mark.parametrize("lang", [None, "fr", "en"])
def test_the_words_outside_the_tab_bar_are_not_tabs(locale, lang):
    locale(lang)
    assert _matches(CAMERA_AND_CAROUSEL, NAVIGATION_SELECTORS.home_tab) == []
    assert _matches(CAMERA_AND_CAROUSEL, NAVIGATION_SELECTORS.search_tab) == []


@pytest.mark.parametrize("lang", [None, "fr", "en"])
def test_the_tabs_of_the_tab_bar_are_still_found(locale, lang):
    locale(lang)
    assert f"{IG}:id/feed_tab" in _matches(FEED, NAVIGATION_SELECTORS.home_tab)
    assert f"{IG}:id/search_tab" in _matches(FEED, NAVIGATION_SELECTORS.search_tab)


def test_the_localized_fallback_finds_a_tab_without_its_id(locale):
    """What the fallback is for: a tab-bar tab whose id the base selector does not know."""
    bar = _instagram(_node(IG, "tab_bar", bounds="[0,1907][1080,2028]", children=(
        _node(IG, desc="Accueil", bounds="[0,1907][216,2028]")
        + _node(IG, desc="Home", bounds="[216,1907][432,2028]")
        + _node(IG, desc="Rechercher et explorer", bounds="[648,1907][864,2028]"))))
    locale("fr")
    assert _matches(bar, NAVIGATION_SELECTORS.home_tab) == ["Accueil"]
    assert _matches(bar, NAVIGATION_SELECTORS.search_tab) == ["Rechercher et explorer"]
    locale("en")
    assert _matches(bar, NAVIGATION_SELECTORS.home_tab) == ["Home"]


class _Phone:
    """A Pixel 3: the launcher or Instagram, Back pops one Instagram screen, a tap on the home
    tab shows the feed, `app_start` opens Instagram on its feed."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2160}
    BACK = {OWN_FOLLOWERS: OWN_PROFILE, OWN_PROFILE: FEED}

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
        hit = None
        for node in etree.fromstring(self.screen.encode("utf-8")).iter("node"):
            left, top, right, bottom = map(int, node.get("bounds").replace("][", ",").strip("[]").split(","))
            if left <= x < right and top <= y < bottom and (node.get("resource-id") or node.get("content-desc")):
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


def test_from_the_own_followers_list_it_backs_out_then_taps_home(no_wait, locale):
    locale("fr")
    ok, phone = _go_home(OWN_FOLLOWERS)
    assert ok
    assert phone.started == []
    assert phone.taps == [(IG, f"{IG}:id/feed_tab")]
    assert phone.screen == FEED
