"""A phone that plays the real screens of a profile search, for the tests of the production search.

Each screen is a real dump, anonymized, of one phone in French: its home feed with the tab bar, the
Explore grid with its search bar, then the results Instagram listed for the query typed there.
- Instagram 410 (Pixel 3, 1080x2160): `ig410_fr_home_feed_tab_icon_selected.xml`,
  `ig410_fr_explore_grid_1080x2160.xml`, `ig410_fr_account_search_results.xml` (account rows
  `user_1` to `user_4`).
- Instagram 447 (Pixel 6a, 1080x2400, 2026-09-28): `ig447_fr_home_feed.xml`,
  `ig447_fr_explore_grid.xml`, `ig447_fr_search_account_only_in_keyword_row.xml`: the account typed
  (`user_3`) has no account row, only keyword rows that name it; the account rows are others', the
  first of them `user_3x`, whose handle holds the query.

The phone moves as Instagram did: a tap on the tab bar's search tab opens Explore, a text typed
there by the keyboard shows the results. Nothing else moves the screen: a tap on a result row is
recorded and the screen stays (what the profile then shows is another test's). It answers `xpath`
through uiautomator2's own engine; the tests put it behind the clone proxy and the facade the
bridges mount.
"""

from dataclasses import dataclass

from lxml import etree
from uiautomator2.xpath import XPathEntry

from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
ROW_ID = f"{PKG}:id/row_search_user_container"
ROW_USERNAME_ID = f"{PKG}:id/row_search_user_username"
SEARCH_TAB_ID = f"{PKG}:id/search_tab"


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
    """The three screens of one search, on one phone."""

    home: str
    explore: str
    results: str
    width: int
    height: int

    def search_tab(self, screen: str):
        nodes = [n for n in etree.fromstring(screen.encode("utf-8")).iter("node")
                 if n.get("resource-id") == SEARCH_TAB_ID]
        return _bounds(nodes[0]) if nodes else None

    def account_rows(self) -> dict:
        """handle -> bounds of its account row, on the results."""
        rows = {}
        for row in etree.fromstring(self.results.encode("utf-8")).iter("node"):
            if row.get("resource-id") != ROW_ID:
                continue
            for node in row.iter("node"):
                if node.get("resource-id") == ROW_USERNAME_ID:
                    rows[node.get("text")] = _bounds(row)
        return rows


SEARCH_410 = SearchScreens(
    home=_capture("ig410_fr_home_feed_tab_icon_selected.xml"),
    explore=_capture("ig410_fr_explore_grid_1080x2160.xml"),
    results=_capture("ig410_fr_account_search_results.xml"),
    width=1080, height=2160,
)
SEARCH_447 = SearchScreens(
    home=_capture("ig447_fr_home_feed.xml"),
    explore=_capture("ig447_fr_explore_grid.xml"),
    results=_capture("ig447_fr_search_account_only_in_keyword_row.xml"),
    width=1080, height=2400,
)


class SearchPhone:
    """uiautomator2, playing the screens of `screens` from the home feed."""

    wait_timeout = 1.0

    def __init__(self, screens: SearchScreens):
        self.screens = screens
        self.screen = screens.home
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
        """The handles of the account rows a tap landed in, in order."""
        rows = self.screens.account_rows()
        return [handle for tap in self.taps for handle, box in rows.items() if _inside(tap, box)]
