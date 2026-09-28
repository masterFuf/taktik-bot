"""Every reader of a profile's posts grid shows the grid before it reads it.

The row under a profile's header has up to four sub-tabs: the posts grid, Reels, Reposts, Tagged.
Instagram keeps the one our own profile was left on until the app restarts (Pixel 3a, Instagram
410 in English: left on Reels, the own profile came back on Reels from the home feed), and a
visited profile shows the last one tapped on it. Only the grid holds post thumbnails. The readers
that looked for them on another sub-tab scrolled the page twice for nothing, stopped a Reel exit,
opened no post for the persona analysis, or counted the header's avatars as posts.

The screens are real dumps, anonymised: the own profile left on Reels, Reposts and Tagged, and its
empty grid (Pixel 3a, 410, English); a visited public profile left on Reels and on Tagged, and its
grid (same phone); the own profile left on Reels and its grid (Pixel 3, 410, French). The phone
below replays them behind the facade and the clone-aware proxy production mounts: a tap on a
sub-tab shows that sub-tab's capture, a tap on a thumbnail opens a post.
"""

from pathlib import Path

import pytest
from loguru import logger
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
from taktik.core.social_media.instagram.actions.atomic.navigation.profile_grid import (
    show_profile_posts_grid,
)
from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
    LikeOrchestration,
)
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS
from taktik.core.social_media.instagram.workflows.common import post_navigation as common_navigation

IG = "com.instagram.android"
FIXTURES = Path(__file__).parent / "fixtures"
SUB_TAB_ROW = f"{IG}:id/profile_tab_layout"
THUMBNAIL = DETECTION_SELECTORS.post_thumbnail_selectors[0]


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


# Per profile: the capture of each sub-tab this test holds, by its label.
OWN_EN = {
    "Grid view": _capture("ig410_en_own_profile_grid_empty.xml"),
    "Reels": _capture("ig410_en_own_profile_left_on_reels.xml"),
    "Reposted": _capture("ig410_en_own_profile_left_on_reposts.xml"),
    "Photos of you": _capture("ig410_en_own_profile_left_on_tagged.xml"),
}
VISITED_EN = {
    "Grid view": _capture("ig410_en_profile_grid.xml"),
    "Reels": _capture("ig410_en_profile_left_on_reels.xml"),
    "Photos of you": _capture("ig410_en_profile_left_on_tagged.xml"),
}
OWN_FR = {
    "Vue Grille": _capture("ig410_fr_own_profile_after_cold_start.xml"),
    "Reels": _capture("ig410_fr_own_profile_left_on_reels.xml"),
}
POST_OPENED = _capture("ig410_fr_post_opened_from_grid.xml")

LEFT_ON_ANOTHER_SUB_TAB = [
    (OWN_EN, "Reels", "Grid view"),
    (OWN_EN, "Reposted", "Grid view"),
    (OWN_EN, "Photos of you", "Grid view"),
    (VISITED_EN, "Reels", "Grid view"),
    (VISITED_EN, "Photos of you", "Grid view"),
    (OWN_FR, "Reels", "Vue Grille"),
]
ON_THE_GRID = [(OWN_EN, "Grid view"), (VISITED_EN, "Grid view"), (OWN_FR, "Vue Grille")]
WITHOUT_SUB_TABS = [
    "ig410_fr_home_feed.xml",
    "ig410_en_hashtag_page.xml",
    "ig447_fr_hashtag_page.xml",
    "ig410_fr_post_opened_from_grid.xml",
]
PROFILES_WITH_SUB_TABS = [
    "ig410_fr_own_profile.xml",
    "ig410_en_own_profile.xml",
    "ig410_fr_own_profile_professional.xml",
    "ig410_fr_profile_opened_from_search.xml",
    "ig410_fr_own_profile_after_cold_start.xml",
    "ig447_fr_own_profile_professional.xml",
    "ig447_fr_profile_verified_business.xml",
    "ig410_en_own_profile_grid_empty.xml",
    "ig410_en_own_profile_left_on_reels.xml",
    "ig410_en_own_profile_left_on_reposts.xml",
    "ig410_en_own_profile_left_on_tagged.xml",
    "ig410_en_profile_grid.xml",
    "ig410_en_profile_left_on_reels.xml",
    "ig410_en_profile_left_on_tagged.xml",
    "ig410_fr_own_profile_left_on_reels.xml",
]


class _Clock:
    """Each reading of the time moves it on a little, each sleep by its length."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        self.now += 0.05
        return self.now

    def sleep(self, seconds=0.0, *_a, **_k):
        self.now += max(0.0, float(seconds))


class _Phone:
    """uiautomator2's own xpath engine on the captures of one profile.

    A tap on a sub-tab shows that sub-tab's capture; a tap on a thumbnail opens a post. Every tap
    is listed by what it landed on, every scroll of the page too."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2220}

    def __init__(self, screens, shown):
        self.screens = screens
        self.screen = screens[shown]
        self.taps = []
        self.scrolls = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def app_current(self):
        return {"package": IG}

    def window_size(self):
        return 1080, 2220

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def click(self, x, y):
        tree = parse_ui_dump(self.screen.encode("utf-8"))
        sub_tab = self._sub_tab_under(tree, x, y)
        if sub_tab is not None:
            self.taps.append(sub_tab)
            if sub_tab in self.screens:
                self.screen = self.screens[sub_tab]
            return
        for cell in tree.xpath(THUMBNAIL):
            if _inside(cell, x, y):
                self.taps.append("thumbnail")
                self.screen = POST_OPENED
                return
        self.taps.append(f"elsewhere ({x}, {y})")

    @staticmethod
    def _sub_tab_under(tree, x, y):
        """The label of the sub-tab whose cell holds the point: the icon's ancestor that sits
        directly in the row, whatever the nesting of each Instagram build."""
        for icon in tree.xpath(PROFILE_SELECTORS.profile_sub_tabs):
            cells = icon.xpath(f'ancestor::*[parent::*[parent::*[@resource-id="{SUB_TAB_ROW}"]]]')
            if cells and _inside(cells[0], x, y):
                return icon.get("content-desc")
        return None

    def press(self, *_a, **_k):
        return True


def _inside(node, x, y):
    left, top, right, bottom = map(int, node.get("bounds").replace("][", ",").strip("[]").split(","))
    return left <= x < right and top <= y < bottom


def _facade(phone):
    return DeviceFacade(CloneAwareDeviceProxy(phone, IG))


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    import time

    clock = _Clock()
    monkeypatch.setattr(time, "time", clock.time)
    monkeypatch.setattr(time, "monotonic", clock.time)
    monkeypatch.setattr(time, "sleep", clock.sleep)
    monkeypatch.setattr("taktik.core.shared.diagnostics.miss_capture.signaler_ecran_inconnu",
                        lambda *_a, **_k: None)
    return clock


def _navigator(phone):
    """The production carrier of the grid readers of the like workflow, built as the Lab and the
    posts scraping build it; its page scrolls are listed on the phone."""
    navigator = LikeOrchestration(_facade(phone))
    navigator.logger = logger

    def scroll(context, distance_ratio, coast=False):
        phone.scrolls.append(context)
        return True

    navigator._session_grid_scroll = scroll
    return navigator


# ── What the captures say ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("screen", PROFILES_WITH_SUB_TABS)
def test_the_first_sub_tab_is_the_grid_and_one_sub_tab_is_shown(screen):
    tree = parse_ui_dump(_capture(screen).encode("utf-8"))
    sub_tabs = tree.xpath(PROFILE_SELECTORS.profile_sub_tabs)
    assert len(sub_tabs) >= 2
    assert sum(tab.get("selected") == "true" for tab in sub_tabs) == 1
    if sub_tabs[0].get("selected") == "true":
        assert tree.xpath(THUMBNAIL) or tree.xpath(PROFILE_SELECTORS.posts_grid_empty_state)
    else:
        assert tree.xpath(THUMBNAIL) == []


@pytest.mark.parametrize("screen", WITHOUT_SUB_TABS)
def test_screens_without_a_profile_have_no_sub_tab(screen):
    tree = parse_ui_dump(_capture(screen).encode("utf-8"))
    assert tree.xpath(PROFILE_SELECTORS.profile_sub_tabs) == []


# ── The one place that shows the grid ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("screens, shown, grid", LEFT_ON_ANOTHER_SUB_TAB)
def test_a_profile_left_on_another_sub_tab_gets_the_grid_tapped(screens, shown, grid):
    phone = _Phone(screens, shown)
    result = show_profile_posts_grid(_facade(phone))
    assert phone.taps == [grid]
    assert (result.found_on, result.tapped, result.shown) == (shown, True, True)
    assert result.photo is not None and result.photo.xml == screens[grid]


@pytest.mark.parametrize("screens, grid", ON_THE_GRID)
def test_a_profile_on_its_grid_is_left_alone(screens, grid):
    phone = _Phone(screens, grid)
    result = show_profile_posts_grid(_facade(phone))
    assert phone.taps == []
    assert (result.found_on, result.tapped, result.shown) == (grid, False, True)


@pytest.mark.parametrize("screen", WITHOUT_SUB_TABS)
def test_nothing_is_tapped_where_there_is_no_sub_tab(screen):
    phone = _Phone({"": _capture(screen)}, "")
    result = show_profile_posts_grid(_facade(phone))
    assert phone.taps == []
    assert (result.has_sub_tabs, result.shown) == (False, False)


def test_the_bare_device_of_a_workflow_is_served_too():
    """The scraping workflows and the persona bridge hold the proxy, not the facade."""
    phone = _Phone(OWN_FR, "Reels")
    show_profile_posts_grid(CloneAwareDeviceProxy(phone, IG))
    assert phone.taps == ["Vue Grille"]


# ── Every reader goes through it ──────────────────────────────────────────────────────────────

def test_the_like_workflow_reads_the_grid_it_selected():
    phone = _Phone(VISITED_EN, "Reels")
    cells = _navigator(phone)._visible_grid_thumbnails(THUMBNAIL)
    assert phone.taps == ["Grid view"]
    assert phone.scrolls == []
    assert len(cells) == 6


def test_the_entry_post_opens_from_the_grid_without_scrolling_first():
    phone = _Phone(VISITED_EN, "Reels")
    assert _navigator(phone)._open_entry_post_of_profile(0, username="visited")
    assert phone.taps == ["Grid view", "thumbnail"]
    assert phone.scrolls == []


def test_a_reel_exit_reopens_from_the_grid():
    """After a Reel, the reopen stopped the visit when the profile showed another sub-tab."""
    phone = _Phone(VISITED_EN, "Reels")
    assert _navigator(phone)._open_entry_post_of_profile(0, username="visited", reopening=True)
    assert phone.taps == ["Grid view", "thumbnail"]


def test_a_post_by_position_opens_from_the_grid():
    phone = _Phone(VISITED_EN, "Photos of you")
    assert _navigator(phone)._open_post_at_position(2)
    assert phone.taps == ["Grid view", "thumbnail"]
    assert phone.scrolls == []


def test_the_first_post_of_the_own_profile_opens_from_the_grid():
    phone = _Phone(OWN_FR, "Reels")
    assert _navigator(phone)._open_first_post_of_profile()
    assert phone.taps == ["Vue Grille", "thumbnail"]
    assert phone.scrolls == []


def test_the_scrapings_first_post_opens_from_the_grid():
    phone = _Phone(OWN_FR, "Reels")
    assert common_navigation.open_first_post_of_profile(CloneAwareDeviceProxy(phone, IG), logger)
    assert phone.taps == ["Vue Grille", "thumbnail"]


def test_the_persona_scan_opens_its_posts_from_the_grid(monkeypatch):
    phone = _Phone(OWN_FR, "Reels")
    monkeypatch.setattr(common_navigation, "human_scroll_raw",
                        lambda _device, direction, **_k: phone.scrolls.append(direction))
    assert common_navigation.open_post_at_position(CloneAwareDeviceProxy(phone, IG), 1, logger)
    assert phone.taps == ["Vue Grille", "thumbnail"]
    assert phone.scrolls == []


@pytest.mark.parametrize("screens, shown, grid", [
    (VISITED_EN, "Reels", "Grid view"),
    (OWN_FR, "Reels", "Vue Grille"),
])
def test_the_profile_visit_counts_the_posts_of_the_grid(screens, shown, grid):
    phone = _Phone(screens, shown)
    count = DetectionActions(_facade(phone)).count_visible_posts()
    assert phone.taps == [grid]
    tree = parse_ui_dump(screens[grid].encode("utf-8"))
    assert count == len(tree.xpath(THUMBNAIL))
