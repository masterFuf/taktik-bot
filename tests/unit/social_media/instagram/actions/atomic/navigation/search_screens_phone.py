"""A phone that plays the real screens of a profile search, for the tests of the production search.

Each screen is a real dump, anonymized, of one phone in French: its home feed with the tab bar, the
Explore grid with its search bar, then the results Instagram listed for the query typed there.
- Instagram 410 (Pixel 3, 1080x2160): `ig410_fr_home_feed_tab_icon_selected.xml`,
  `ig410_fr_explore_grid_1080x2160.xml`, `ig410_fr_account_search_results.xml` (account rows
  `user_1` to `user_4`).
- Instagram 447 (Pixel 6a, 1080x2400, 2026-09-28): `ig447_fr_home_feed.xml`,
  `ig447_fr_explore_grid.xml`, `ig447_fr_search_account_only_in_keyword_row.xml`: the account typed
  (`user_3`) has no account row, only keyword rows that name it, the first one in its subtitle
  ("user_3 • 104 M followers") under a title that is another query; the account rows are others',
  the first of them `user_3x`, whose handle holds the query.
- Instagram 447 (same phone, 2026-10-24), the same home and Explore, then
  `ig447_fr_search_keyword_row_names_the_handle.xml`: "nasa" typed, here `name_1`, listed only in a
  keyword row titled by its handle ("name_1", "name_1 • 104 M followers"), then the keyword rows of
  two neighbours whose handles hold it (`name_1s`, `name_1e`: the anonymizer's names for them,
  renamed so that they keep the query at their start as on the phone), and account rows of others,
  the first of them `name_11`.
- Instagram 447 (same phone, 2026-10-24), a cold DM started where an earlier run had left the
  phone: a likers sheet over a post (`ig447_fr_likers_sheet_over_post_after_search.xml`), the post
  under it (`ig447_fr_post_opened_from_search_profile.xml`), the profile it was opened from
  (`ig447_fr_profile_opened_from_search.xml`), then the results of the search that opened that
  profile (`ig447_fr_search_results_left_open.xml`, "natgeo" typed, here `name_21`). None of them
  shows the tab bar. Anonymized together: a name reads the same on the four screens.

The phone moves as Instagram did: a tap on the tab bar's search tab opens Explore, a text typed
there by the keyboard shows the results, a Back shows the screen under the one shown (when the
phone was given what is under it). Nothing else moves the screen: a tap on a result row is
recorded and the screen stays (what the profile then shows is another test's). It answers `xpath`
through uiautomator2's own engine; the tests put it behind the clone proxy and the facade the
bridges mount, with the selectors the version of the screens gets at connect (`selectors_of`).
"""

from contextlib import contextmanager
from dataclasses import dataclass

from lxml import etree
from uiautomator2.xpath import XPathEntry

from taktik.core.compat.selectors.setup import INSTAGRAM_TARGET_VERSION, apply_version_overrides
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
ROW_ID = f"{PKG}:id/row_search_user_container"
ROW_USERNAME_ID = f"{PKG}:id/row_search_user_username"
KEYWORD_TITLE_ID = f"{PKG}:id/search_keyword_title"
KEYWORD_SUBTITLE_ID = f"{PKG}:id/row_search_keyword_subtitle"
AVATAR_RING_ID = f"{PKG}:id/row_search_avatar_with_ring"
SEARCH_TAB_ID = f"{PKG}:id/search_tab"
#: What follows the handle in the subtitle of a keyword row: "nasa • 104 M followers".
KEYWORD_SUBTITLE_SEPARATOR = " • "


def _capture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _bounds(node):
    left_top, right_bottom = node.get("bounds").strip("[]").split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


def _inside(point, box) -> bool:
    x, y = point
    left, top, right, bottom = box
    return left <= x <= right and top <= y <= bottom


@dataclass(frozen=True)
class SearchScreens:
    """The three screens of one search, on one phone, and the Instagram version they show."""

    home: str
    explore: str
    results: str
    width: int
    height: int
    version: str

    def search_tab(self, screen: str):
        nodes = [n for n in etree.fromstring(screen.encode("utf-8")).iter("node")
                 if n.get("resource-id") == SEARCH_TAB_ID]
        return _bounds(nodes[0]) if nodes else None

    def result_rows(self) -> list:
        """(handle, bounds) of each row of the results that names an account: an account row by
        its username, a keyword row by the handle its subtitle starts with."""
        rows = []
        for row in etree.fromstring(self.results.encode("utf-8")).iter("node"):
            if row.get("resource-id") == ROW_ID:
                rows += [(node.get("text"), _bounds(row)) for node in row.iter("node")
                         if node.get("resource-id") == ROW_USERNAME_ID]
            elif row.get("resource-id") == KEYWORD_TITLE_ID:
                rows += [(node.get("text").split(KEYWORD_SUBTITLE_SEPARATOR)[0], _bounds(row.getparent()))
                         for node in row if node.get("resource-id") == KEYWORD_SUBTITLE_ID]
        return rows

    def avatar_rings(self) -> list:
        """The bounds of the avatar rings of the results, each a button that opens a story."""
        return [_bounds(node) for node in etree.fromstring(self.results.encode("utf-8")).iter("node")
                if node.get("resource-id") == AVATAR_RING_ID]


SEARCH_410 = SearchScreens(
    home=_capture("ig410_fr_home_feed_tab_icon_selected.xml"),
    explore=_capture("ig410_fr_explore_grid_1080x2160.xml"),
    results=_capture("ig410_fr_account_search_results.xml"),
    width=1080, height=2160, version=INSTAGRAM_TARGET_VERSION,
)
SEARCH_447 = SearchScreens(
    home=_capture("ig447_fr_home_feed.xml"),
    explore=_capture("ig447_fr_explore_grid.xml"),
    results=_capture("ig447_fr_search_account_only_in_keyword_row.xml"),
    width=1080, height=2400, version="447.0.0.55.81",
)
SEARCH_447_KEYWORD_ROW = SearchScreens(
    home=_capture("ig447_fr_home_feed.xml"),
    explore=_capture("ig447_fr_explore_grid.xml"),
    results=_capture("ig447_fr_search_keyword_row_names_the_handle.xml"),
    width=1080, height=2400, version="447.0.0.55.81",
)
SEARCH_447_LEFT_OPEN = SearchScreens(
    home=_capture("ig447_fr_home_feed.xml"),
    explore=_capture("ig447_fr_explore_grid.xml"),
    results=_capture("ig447_fr_search_results_left_open.xml"),
    width=1080, height=2400, version="447.0.0.55.81",
)
#: What an earlier run left on the phone of `SEARCH_447_LEFT_OPEN`, top first: the likers sheet,
#: then what each Back showed under it, down to the results of the search.
LEFT_OPEN_STACK = (
    _capture("ig447_fr_likers_sheet_over_post_after_search.xml"),
    _capture("ig447_fr_post_opened_from_search_profile.xml"),
    _capture("ig447_fr_profile_opened_from_search.xml"),
    SEARCH_447_LEFT_OPEN.results,
)


@contextmanager
def selectors_of(screens: SearchScreens):
    """The selector catalogues as a phone of `screens` gets them at connect: its version's
    overrides applied, the baseline put back after."""
    apply_version_overrides("instagram", screens.version)
    try:
        yield
    finally:
        apply_version_overrides("instagram", INSTAGRAM_TARGET_VERSION)


class SearchPhone:
    """uiautomator2, playing the screens of `screens` from the home feed, or from the first screen
    of `stack` (each Back then shows the next one; on the last, a Back changes nothing)."""

    wait_timeout = 1.0

    def __init__(self, screens: SearchScreens, stack=()):
        self.screens = screens
        self.stack = list(stack)
        self.screen = self.stack.pop(0) if self.stack else screens.home
        self.info = {"displayWidth": screens.width, "displayHeight": screens.height}
        self.taps = []
        self.typed = []
        self.presses = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def app_current(self):
        return {"package": PKG}

    def window_size(self):
        return self.screens.width, self.screens.height

    def press(self, key, meta=None):
        self.presses.append(key)
        if key == "back" and self.stack:
            self.screen = self.stack.pop(0)
        return True

    def click(self, x, y):
        self.taps.append((x, y))
        tab = self.screens.search_tab(self.screen)
        if self.screen is self.screens.home and tab and _inside((x, y), tab):
            self.screen = self.screens.explore

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def keyboard_types(self, text: str) -> None:
        """What the Taktik Keyboard types into the focused field."""
        self.typed.append(text)
        if self.screen is self.screens.explore:
            self.screen = self.screens.results

    def rows_tapped(self) -> list:
        """The handles of the result rows a tap landed in, in order."""
        rows = self.screens.result_rows()
        return [handle for tap in self.taps for handle, box in rows if _inside(tap, box)]

    def avatar_rings_tapped(self) -> list:
        """The taps that landed on an avatar ring of the results."""
        rings = self.screens.avatar_rings()
        return [tap for tap in self.taps if any(_inside(tap, ring) for ring in rings)]
