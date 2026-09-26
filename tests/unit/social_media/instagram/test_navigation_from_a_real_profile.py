"""Going home, and reopening a grid post, from a real profile screen.

The screen is a real dump (Pixel 3, IG 410 in French, a profile opened through the search: no tab
bar, Instagram's own back arrow), anonymized: every text emptied, content-desc kept only for
structural labels, grid cells renamed (`fixtures/ig410_fr_profile_opened_from_search.xml`).

Each case is run twice: on a phone that obeys (what must happen) and on one that obeys nothing
(the screen a run saw for minutes, while its Backs and taps went nowhere): the code must still
send its Backs, stop, and never press anything else.
"""

import time as real_time
from pathlib import Path

import pytest
from loguru import logger
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as base_action_module
import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.business.actions.like.post_navigation as post_navigation_module
import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.instagram.actions.atomic.navigation.tab_navigation import TabNavigationMixin
from taktik.core.social_media.instagram.actions.business.actions.like.post_navigation import PostNavigationMixin
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_SELECTORS

PKG = "com.instagram.android"
PROFILE = (Path(__file__).parent / "fixtures" / "ig410_fr_profile_opened_from_search.xml").read_text(encoding="utf-8")
GRID_CELL = f'//*[@resource-id="{PKG}:id/image_button"]'
FEED_TAB = (0, 1907, 216, 2028)


class _Clock:
    """`_find_and_click` waits on `time.time()`: a clock that runs, and sleeps that do not."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        self.now += 0.7
        return self.now

    def sleep(self, _seconds):
        pass

    def __getattr__(self, name):
        return getattr(real_time, name)


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, post_navigation_module):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(base_action_module, "time", _Clock())
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    monkeypatch.setattr(miss_capture, "blocage_a_signaler", lambda: False)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _node(rid, desc="", bounds=(0, 0, 10, 10), selected=False, children="", package=PKG):
    left, top, right, bottom = bounds
    rid = f"{package}:id/{rid}" if rid else ""
    return (f'<node index="0" text="" resource-id="{rid}" class="android.widget.FrameLayout" package="{package}" '
            f'content-desc="{desc}" clickable="true" enabled="true" focused="false" '
            f'selected="{str(selected).lower()}" bounds="[{left},{top}][{right},{bottom}]">{children}</node>')


def _screen(*nodes):
    nav_bar = (_node("back", "Retour", (129, 2028, 349, 2160), package="com.android.systemui")
               + _node("home_button", "Accueil", (430, 2028, 650, 2160), package="com.android.systemui"))
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            + _node("", bounds=(0, 0, 1080, 2028), children="".join(nodes)) + nav_bar + "</hierarchy>")


def _tab_bar(home_selected=False):
    # IG 410 names its home tab "Home" even in French.
    tabs = [("feed_tab", "Home", home_selected), ("clips_tab", "Reels", False),
            ("direct_tab", "Envoyer un message", False), ("search_tab", "Rechercher et explorer", not home_selected),
            ("profile_tab", "Profil", False)]
    return _node("tab_bar", bounds=(0, 1907, 1080, 2028), children="".join(
        _node(rid, desc, (216 * i, 1907, 216 * (i + 1), 2028), selected)
        for i, (rid, desc, selected) in enumerate(tabs)))


SEARCH_RESULTS = _screen(_node("action_bar_button_back", "Retour", (0, 77, 132, 231)),
                         _node("row_search_user_container", bounds=(0, 300, 1080, 450)))
EXPLORE = _screen(_node("action_bar_search_edit_text", bounds=(33, 77, 937, 174)), _tab_bar())
HOME = _screen(_node("reels_tray_container", bounds=(0, 231, 1080, 578)), _tab_bar(home_selected=True))
POST = _screen(_node("action_bar_button_back", "Retour", (0, 77, 132, 231)),
               _node("row_feed_button_like", bounds=(0, 1500, 120, 1600)))


def _inside(point, bounds):
    x, y = point
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


class _Phone:
    """uiautomator2 behind the proxy and the facade. `obeys=False`: the screen never moves."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2160}

    def __init__(self, screen, obeys=True, backs=(), taps=None):
        self.screen = screen
        self.obeys = obeys
        self.back_stack = list(backs)
        self.tap_to = taps or (lambda screen, point: None)
        self.presses = []
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def app_current(self):
        return {"package": PKG}

    def window_size(self):
        return 1080, 2160

    def press(self, key, meta=None):
        if key not in ("back", "home", "enter", "delete", "del"):
            return False
        self.presses.append(key)
        if self.obeys and key == "back" and self.back_stack:
            self.screen = self.back_stack.pop(0)
        return True

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def click(self, x, y):
        self.taps.append((x, y))
        if self.obeys:
            self.screen = self.tap_to(self.screen, (x, y)) or self.screen


def _facade(phone):
    return DeviceFacade(CloneAwareDeviceProxy(phone, PKG))


# ── navigation.go_home from the profile ──────────────────────────────────────────────────────

def _tap_home_tab(screen, point):
    return HOME if screen is EXPLORE and _inside(point, FEED_TAB) else None


def _navigation(phone):
    nav = object.__new__(TabNavigationMixin)
    nav.device = _facade(phone)
    nav.logger = logger.bind(module="test_navigation_from_a_real_profile")
    nav.selectors = NAVIGATION_SELECTORS
    nav.detection_selectors = DETECTION_SELECTORS
    nav._method_stats = {"clicks": 0, "waits": 0, "sleeps": 0, "errors": 0}
    nav._platform = "instagram"
    nav._human_like_delay = lambda *a, **k: None
    return nav


def test_the_real_profile_is_not_a_root_screen():
    assert _facade(_Phone(PROFILE)).is_on_root_screen() is False


def test_going_home_from_the_profile_backs_out_to_the_tab_bar_then_taps_home():
    phone = _Phone(PROFILE, backs=[SEARCH_RESULTS, EXPLORE], taps=_tap_home_tab)

    assert _navigation(phone).navigate_to_home() is True
    assert phone.presses == ["back", "back"]
    assert phone.screen is HOME
    assert _inside(phone.taps[-1], FEED_TAB)


def test_on_a_phone_that_obeys_nothing_going_home_sends_its_three_backs_and_stops():
    phone = _Phone(PROFILE, obeys=False)

    assert _navigation(phone).navigate_to_home() is False
    assert phone.presses == ["back", "back", "back"]
    assert phone.taps == []


# ── post.return_to_grid_and_reopen: the reopen, on the profile grid ──────────────────────────

class _Planner:
    def _plan_behavior_gesture(self, *_a, **_k):
        return {"distance_scale": 1.0, "velocity_scale": 1.0, "settle_scale": 1.0}


def _grid_cells():
    return [tuple(el.bounds) for el in _Phone(PROFILE).xpath(GRID_CELL).all()]


def _reopener(phone):
    host = object.__new__(PostNavigationMixin)
    host.device = _facade(phone)
    host.logger = logger.bind(module="test_navigation_from_a_real_profile")
    host.detection_selectors = DETECTION_SELECTORS
    host.post_selectors = POST_SELECTORS
    host.scroll_actions = _Planner()
    host.behavior_state = None
    return host


def test_the_real_profile_grid_shows_its_six_cells():
    cells = _grid_cells()
    assert len(cells) == 6
    assert cells[0] == (0, 1451, 358, 1928)


def test_reopening_a_grid_post_taps_inside_a_cell_and_opens_it():
    cells = _grid_cells()
    phone = _Phone(PROFILE, taps=lambda screen, point: POST if any(_inside(point, c) for c in cells) else None)

    assert _reopener(phone)._open_entry_post_of_profile(0, reopening=True) is True
    assert len(phone.taps) == 1 and any(_inside(phone.taps[0], c) for c in cells)
    assert phone.presses == []


def test_on_a_phone_that_obeys_nothing_the_reopen_taps_once_and_gives_up():
    phone = _Phone(PROFILE, obeys=False)

    assert _reopener(phone)._open_entry_post_of_profile(0, reopening=True) is False
    assert len(phone.taps) == 1
    assert phone.presses == []
