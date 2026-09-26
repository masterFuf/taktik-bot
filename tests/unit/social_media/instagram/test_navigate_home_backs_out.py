"""From a screen without the tab bar (a reel viewer, a search in progress), going home backs out
one screen at a time. Those Backs went through the Instagram facade's press("back"), a key name
uiautomator2 ignores, so the fallback never moved and every workflow parked there stayed there.

The fake device ignores key names it does not know, as uiautomator2 does.
"""

from taktik.core.social_media.instagram.actions.atomic.navigation.tab_navigation import TabNavigationMixin
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade as InstagramDeviceFacade


class _Uiautomator2:
    """Takes the key NAMES uiautomator2 knows, ignores the rest without an error."""
    KNOWN_KEYS = {"back", "home", "enter", "delete"}

    def __init__(self, screens_to_home, tab_bar_after=None):
        self.screens_to_home = screens_to_home
        self.tab_bar_after = tab_bar_after
        self.backs = 0

    def press(self, key):
        if key == "back":
            self.backs += 1
            self.screens_to_home -= 1


def _facade(raw):
    facade = object.__new__(InstagramDeviceFacade)
    facade._device = raw
    facade.logger = __import__("loguru").logger
    return facade


def _navigation(raw):
    nav = object.__new__(TabNavigationMixin)
    nav.device = _facade(raw)
    nav.logger = __import__("loguru").logger
    nav.selectors = type("S", (), {"home_tab": []})()
    nav._navigate_to_tab = lambda *a, **k: raw.tab_bar_after is not None and raw.backs >= raw.tab_bar_after
    nav._is_home_screen = lambda: raw.screens_to_home <= 0
    nav._is_instagram_open = lambda: True
    nav._human_like_delay = lambda *a, **k: None
    return nav


def test_going_home_from_a_reel_viewer_backs_out_and_stops_on_the_feed():
    raw = _Uiautomator2(screens_to_home=2)
    assert _navigation(raw).navigate_to_home()
    assert raw.backs == 2


def test_it_never_backs_more_than_three_screens():
    raw = _Uiautomator2(screens_to_home=5)
    assert not _navigation(raw).navigate_to_home()
    assert raw.backs == 3


def test_once_a_back_brings_the_tab_bar_back_home_is_one_tap_away():
    """A reel opened from a search: reel, hashtag, results, then the search page with its tab bar."""
    raw = _Uiautomator2(screens_to_home=5, tab_bar_after=3)
    assert _navigation(raw).navigate_to_home()
    assert raw.backs == 3
