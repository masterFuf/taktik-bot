"""Nothing the bot taps or presses to go back may take it out of Instagram.

Every dump holds more than Instagram: the Android navigation bar (`com.android.systemui:id/back`
"Retour", `:id/home_button` "Accueil") and, when Instagram is not in front, the launcher
(`accessibility_action_view` "Accueil"). A selector on a label alone taps them: the system Back
leaves the home feed, the launcher gets tapped at random. And a Back KEY on a root screen of
Instagram (home feed, main tabs) leaves Instagram or jumps tab: the facade refuses it.

The phone is uiautomator2's own xpath engine behind the proxy and the facade production mounts;
the dumps are invented, shaped like the Pixel 3 ones (IG 410, 1080x2160).
"""

import logging

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.actions.base_action import SharedBaseAction
from taktik.core.shared.device.snapshot import ScreenSnapshot
from taktik.core.social_media.instagram.actions.business.workflows.feed.suggestions import FeedSuggestionsMixin
from taktik.core.social_media.instagram.actions.business.workflows.feed.suggestions_visit import (
    DiscoverSuggestionsVisitMixin,
)
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.shell.auth import AUTH_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SCROLL_SELECTORS

PKG = "com.instagram.android"
CLONE = "com.taktik.ig1"
SYSTEMUI = "com.android.systemui"
LAUNCHER = "com.google.android.apps.nexuslauncher"


@pytest.fixture(autouse=True)
def _french_app(monkeypatch):
    monkeypatch.setattr(facade_module.time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _node(package, rid, desc="", bounds=(0, 0, 10, 10), cls="android.widget.FrameLayout", focused=False,
          children=""):
    left, top, right, bottom = bounds
    rid = f"{package}:id/{rid}" if rid else ""
    return (f'<node index="0" text="" resource-id="{rid}" class="{cls}" package="{package}" '
            f'content-desc="{desc}" clickable="true" enabled="true" focused="{str(focused).lower()}" '
            f'selected="false" bounds="[{left},{top}][{right},{bottom}]">{children}</node>')


def _nav_bar():
    # French and English labels at once: the selectors of both locales are checked against it.
    return "".join(_node(SYSTEMUI, rid, desc, bounds, "android.widget.ImageView") for rid, desc, bounds in (
        ("back", "Retour", (129, 2028, 349, 2160)), ("home_button", "Accueil", (430, 2028, 650, 2160)),
        ("back", "Back", (129, 2028, 349, 2160)), ("home_button", "Home", (430, 2028, 650, 2160))))


def _tab_bar(package=PKG):
    tabs = [("feed_tab", "Accueil"), ("clips_tab", "Reels"), ("direct_tab", "Envoyer un message"),
            ("search_tab", "Rechercher et explorer"), ("profile_tab", "Profil")]
    return _node(package, "tab_bar", bounds=(0, 1907, 1080, 2028), children="".join(
        _node(package, rid, desc, (216 * i, 1907, 216 * (i + 1), 2028)) for i, (rid, desc) in enumerate(tabs)))


def _screen(*nodes, package=PKG):
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            + _node(package, "", bounds=(0, 0, 1080, 2028), children="".join(nodes)) + _nav_bar()
            + "</hierarchy>")


def home_feed(package=PKG):
    return _screen(_node(package, "reels_tray_container", bounds=(0, 231, 1080, 578)), _tab_bar(package),
                   package=package)


def pushed_profile():
    return _screen(_node(PKG, "action_bar_button_back", "Retour", (0, 77, 132, 231), "android.widget.ImageView"),
                   _node(PKG, "profile_header_container", bounds=(0, 231, 1080, 900)), _tab_bar())


def sheet_over_feed():
    return _screen(_node(PKG, "reels_tray_container", bounds=(0, 231, 1080, 578)), _tab_bar(),
                   _node(PKG, "background_dimmer", bounds=(0, 0, 1080, 2028)),
                   _node(PKG, "layout_container_bottom_sheet", bounds=(0, 700, 1080, 2028)))


def keyboard_over_feed():
    return _screen(_node(PKG, "search_edit_text", bounds=(33, 77, 937, 174), cls="android.widget.EditText",
                         focused=True), _tab_bar())


def story_viewer():
    return _screen(_node(PKG, "reel_viewer_root", bounds=(0, 0, 1080, 2028)))


def launcher():
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            + _node(LAUNCHER, "accessibility_action_view", "Accueil", (0, 77, 1080, 2028), "android.view.View")
            + _node(LAUNCHER, "accessibility_action_view", "Home", (0, 77, 1080, 2028), "android.view.View")
            + _nav_bar() + "</hierarchy>")


class _Phone:
    """uiautomator2 as its server answers: a known key NAME or an int is pressed, the rest ignored."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2160}
    KEY_NAMES = {"home", "back", "enter", "delete", "del", "menu", "search", "recent"}

    def __init__(self, xml):
        self.xml = xml
        self.presses = []
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def press(self, key, meta=None):
        if isinstance(key, int) or str(key).lower() in self.KEY_NAMES:
            self.presses.append(key)
            return True
        return False

    def click(self, x, y):
        self.taps.append((x, y))

    def long_click(self, x, y, _duration=0.0):
        self.taps.append((x, y))

    def window_size(self):
        return 1080, 2160


def _facade(xml, package=PKG):
    phone = _Phone(xml)
    return phone, DeviceFacade(CloneAwareDeviceProxy(phone, package))


def _packages_found(selectors, xml, package=PKG):
    rewrite = CloneAwareDeviceProxy(object(), package).rewrite_xpath
    photo = ScreenSnapshot(xml, rewrite=rewrite)
    found = set()
    for selector in ([selectors] if isinstance(selectors, str) else selectors):
        found |= {el.attrib.get("package") for el in photo.elements(selector)}
    return found


# ── Tabs and back arrows are Instagram's own ─────────────────────────────────────────────────

_TAPPED = {
    "navigation.home_tab": lambda: NAVIGATION_SELECTORS.home_tab,
    "navigation.search_tab": lambda: NAVIGATION_SELECTORS.search_tab,
    "navigation.profile_tab": lambda: NAVIGATION_SELECTORS.profile_tab,
    "navigation.back_button": lambda: NAVIGATION_SELECTORS.back_button,
    "navigation.back_buttons": lambda: NAVIGATION_SELECTORS.back_buttons,
    "feed.back_button_xpath": lambda: FEED_SCROLL_SELECTORS.back_button_xpath,
    "feed.home_tab_xpath": lambda: FEED_SCROLL_SELECTORS.home_tab_xpath,
    "auth.login_success_indicators": lambda: AUTH_SELECTORS.login_success_indicators,
}


@pytest.mark.parametrize("lang", ["fr", "en", None])
@pytest.mark.parametrize("name", sorted(_TAPPED))
def test_no_navigation_selector_reaches_the_android_bar_or_the_launcher(name, lang):
    set_active_locale(lang)
    selectors = _TAPPED[name]()
    for xml in (home_feed(), launcher(), story_viewer()):
        assert _packages_found(selectors, xml) <= {PKG}, name


def test_the_home_tab_is_still_found_in_instagram():
    assert _packages_found(NAVIGATION_SELECTORS.home_tab, home_feed()) == {PKG}
    assert _packages_found(FEED_SCROLL_SELECTORS.home_tab_xpath, home_feed()) == {PKG}


def test_a_clone_is_still_found_through_the_proxy():
    """`@package` is swapped for the clone's by the proxy, as `@resource-id` is made agnostic."""
    label_only = [s for s in NAVIGATION_SELECTORS.home_tab if "@package" in s]
    assert label_only, "the locale home tab entry is expected to name Instagram's package"
    assert _packages_found(label_only, home_feed(CLONE), package=CLONE) == {CLONE}


def test_the_proxy_rewrites_the_package_only_for_a_clone():
    xpath = f'//*[@content-desc="Accueil" and @package="{PKG}"]'
    assert CloneAwareDeviceProxy(object(), CLONE).rewrite_xpath(xpath) == \
        f'//*[@content-desc="Accueil" and @package="{CLONE}"]'
    assert CloneAwareDeviceProxy(object(), PKG).rewrite_xpath(xpath) == xpath
    systemui = f'//*[not(@package="{SYSTEMUI}")]'
    assert CloneAwareDeviceProxy(object(), CLONE).rewrite_xpath(systemui) == systemui


# ── A Back key on a root screen is refused ───────────────────────────────────────────────────

def test_back_is_refused_on_the_home_feed():
    """No tab is marked selected here, as after a cold start: the tab bar alone tells a root."""
    phone, facade = _facade(home_feed())
    assert facade.is_on_root_screen() is True
    assert facade.press("back") is False
    assert facade.back() is False
    assert facade.press(4) is False
    facade.press_back()
    assert phone.presses == []


@pytest.mark.parametrize("screen", [pushed_profile, sheet_over_feed, keyboard_over_feed, story_viewer])
def test_back_still_goes_where_it_closes_or_pops_something(screen):
    phone, facade = _facade(screen())
    assert facade.is_on_root_screen() is False
    assert facade.press("back") is True
    facade.press_back()
    assert phone.presses == ["back", "back"]


def test_an_unreadable_screen_does_not_block_back():
    phone, facade = _facade("")
    assert facade.press("back") is True
    assert phone.presses == ["back"]


def test_a_clone_home_feed_is_a_root_too():
    phone, facade = _facade(home_feed(CLONE), package=CLONE)
    assert facade.press("back") is False
    assert phone.presses == []


# ── The run that closed Instagram (Pixel 3, IG 410, suggestions.back_to_list from the feed) ──

class _SuggestionsHost(DiscoverSuggestionsVisitMixin, FeedSuggestionsMixin):
    _human_tap_element = SharedBaseAction._human_tap_element

    def __init__(self, device):
        self.device = device
        self.logger = logging.getLogger("test_back_stays_in_instagram")

    def _human_like_delay(self, *_a, **_k):
        pass


def test_leaving_a_suggestion_profile_from_the_feed_neither_taps_the_system_back_nor_presses_back():
    phone, facade = _facade(home_feed())
    host = _SuggestionsHost(facade)

    assert host.leave_discover_profile() is False
    assert phone.taps == [], "a tap landed on the Android navigation bar"
    assert phone.presses == []
