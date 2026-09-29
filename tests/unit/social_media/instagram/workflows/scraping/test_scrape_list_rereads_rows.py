"""After a profile the filters set aside, the list is read again before the next tap; and a
profile page is never recorded under the name of another row.

A scrape of a large account's followers with `minPosts: 1` (Pixel 3, IG 410) read the list 7
times for 28 profile visits. A profile the filters set aside went back to the list and
`continue`d on the rows read BEFORE the visit; a kept profile `break`s and reads the list again.
When the list had moved on the way back, the next tap landed on another row: one account was
read twice, and two of the three profiles kept were saved with the counters of their
neighbour. The posts counter itself was right: on the ten 0-post profile captures of the
corpus, the node it reads says "0".

The phone is uiautomator2's own xpath engine behind the facade production mounts
(`CloneAwareDeviceProxy`). Its screens are two real captures of the same followers list
(Instagram 410.0.0.53.71 in French, Pixel 3), anonymized together (a name keeps its value across
both): the top of the list, then the list scrolled up by three rows' worth, as it came back once.
"""

import time

import pytest
from loguru import logger
from lxml import etree
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.ui_dump import parse_bounds
from taktik.core.social_media.instagram.actions.atomic.detection.list_detection import (
    ListDetectionMixin,
)
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.actions.base.utils import ActionUtils
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.workflows.scraping.list_scraping import (
    OTHER_PROFILE_REASON,
    ScrapingListMixin,
)
from taktik.core.social_media.instagram.workflows.scraping.list_strategy import ListScrapingStrategy
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
LIST_TOP = (FIXTURES / "ig410_fr_followers_list_top.xml").read_text(encoding="utf-8")
LIST_SCROLLED = (FIXTURES / "ig410_fr_followers_list_scrolled.xml").read_text(encoding="utf-8")


def _rows(xml):
    """(username, row bounds) of each row of a list screen, top to bottom."""
    rows = []
    for row in etree.fromstring(xml.encode("utf-8")).iter("node"):
        if row.get("resource-id", "").endswith("/follow_list_container"):
            names = [n.get("text") for n in row.iter("node")
                     if n.get("resource-id", "").endswith("/follow_list_username")]
            if names:
                rows.append((names[0], parse_bounds(row.get("bounds"))))
    return rows


class _Phone:
    """A followers list; a tap on a row opens that row's profile."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2160}

    def __init__(self, screen):
        self.screen = screen
        self.opened = None
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def click(self, x, y):
        self.opened = next((name for name, (left, top, right, bottom) in _rows(self.screen)
                            if left <= x <= right and top <= y <= bottom), None)

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def press(self, _key):
        pass

    def window_size(self):
        return 1080, 2160


class _Scraper(ScrapingListMixin):
    """Every profile is set aside by the filters, as 24 of 27 were that night."""

    def __init__(self, phone, visits):
        self.device = phone
        self.logger = logger
        self.config = {"rescrape_after_days": 0}
        self.scraped_profiles = []
        self.visits = []
        self.max_visits = visits
        self.returns = 0

    def _should_continue(self):
        return len(self.visits) < self.max_visits

    def _capture_profile_on_screen(self, username, **_kwargs):
        self.visits.append((username, self.device.opened))
        return "posts < 1"

    def _back_to_list(self, _strategy):
        # On the first way back the list comes back scrolled: its rows sit three rows higher.
        self.returns += 1
        if self.returns == 1:
            self.device.screen = LIST_SCROLLED

    def _save_profile_immediately(self, _profile, source_post_url=None):
        return None


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)


def test_after_a_profile_set_aside_the_next_tap_opens_the_row_it_names():
    phone = _Phone(LIST_TOP)
    detection = object.__new__(ListDetectionMixin)
    detection.device = DeviceFacade(CloneAwareDeviceProxy(phone, PKG))
    detection.detection_selectors = DETECTION_SELECTORS
    detection.utils = ActionUtils()
    detection.logger = logger
    strategy = ListScrapingStrategy(get_visible=detection.get_visible_followers_with_elements,
                                    is_on_list=lambda: True, scroll_down=lambda: None,
                                    enable_suggestions_check=False)
    scraper = _Scraper(phone, visits=3)
    first_three = [name for name, _bounds in _rows(LIST_TOP)[:3]]
    # The trap is on screen: where the second row was, the scrolled list shows another row.
    second_top = _rows(LIST_TOP)[1][1][1]
    assert [name for name, b in _rows(LIST_SCROLLED) if b[1] <= second_top + 50 <= b[3]] != first_three[1:2]

    scraped = scraper._scrape_list(3, "FOLLOWER", "demo", enrich_on_the_fly=True, strategy=strategy)

    assert scraped == []
    assert scraper.visits == [(name, name) for name in first_three]


class _ProfileManager:
    def __init__(self, page):
        self.page = page

    def get_complete_profile_info(self, **_kwargs):
        return dict(self.page)


class _Workflow(ScrapingListMixin):
    def __init__(self, page):
        self.profile_manager = _ProfileManager(page)
        self.logger = logger
        self.config = {"minPosts": 1, "skipPrivateProfiles": False}
        self._ai_service = None


PAGE = {"username": "agbaga_demo", "followers_count": 9, "following_count": 80, "posts_count": 1,
        "full_name": "Demo", "biography": ""}


def test_a_page_of_another_account_is_not_recorded_under_the_row_name():
    data = {"username": "laura_demo"}
    reason = _Workflow(PAGE)._capture_profile_on_screen(username="laura_demo", profile_data=data)
    assert reason == OTHER_PROFILE_REASON
    assert data == {"username": "laura_demo"}


@pytest.mark.parametrize("shown", ["agbaga_demo", "Agbaga_Demo", None])
def test_the_row_own_page_or_an_unread_name_is_kept(shown):
    data = {"username": "agbaga_demo"}
    reason = _Workflow({**PAGE, "username": shown})._capture_profile_on_screen(
        username="agbaga_demo", profile_data=data)
    assert reason is None
    assert data["posts_count"] == 1 and data["followers_count"] == 9
