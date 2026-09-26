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
(`CloneAwareDeviceProxy`); the dumps are invented (public repository).
"""

import time

import pytest
from loguru import logger
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.atomic.detection.list_detection import (
    ListDetectionMixin,
)
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.actions.core.utils import ActionUtils
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.workflows.scraping.list_scraping import (
    OTHER_PROFILE_REASON,
    ScrapingListMixin,
)
from taktik.core.social_media.instagram.workflows.scraping.list_strategy import ListScrapingStrategy

PKG = "com.instagram.android"
ROW_TOPS = (600, 800, 1000)


def _list(names):
    rows = "".join(
        f'<node index="{i}" text="{name}" resource-id="{PKG}:id/follow_list_username" '
        f'class="android.widget.TextView" package="{PKG}" content-desc="" clickable="true" '
        f'enabled="true" bounds="[200,{top}][700,{top + 50}]" />'
        for i, (name, top) in enumerate(zip(names, ROW_TOPS)))
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            f'<node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="{PKG}" '
            f'bounds="[0,0][1080,2400]">{rows}</node></hierarchy>')


class _Phone:
    """A followers list; a tap on a row opens that row's profile."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2400}

    def __init__(self, names):
        self.names = list(names)
        self.opened = None
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return _list(self.names)

    def click(self, x, y):
        self.opened = next((name for name, top in zip(self.names, ROW_TOPS) if top <= y <= top + 50), None)

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def press(self, _key):
        pass

    def window_size(self):
        return 1080, 2400


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
        # On the first way back the list comes back one row further down.
        self.returns += 1
        if self.returns == 1:
            self.device.names = self.device.names[1:] + ["delta_demo"]

    def _save_profile_immediately(self, _profile, source_post_url=None):
        return None


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)


def test_after_a_profile_set_aside_the_next_tap_opens_the_row_it_names():
    phone = _Phone(["alpha_demo", "bravo_demo", "charlie_demo"])
    detection = object.__new__(ListDetectionMixin)
    detection.device = DeviceFacade(CloneAwareDeviceProxy(phone, PKG))
    detection.detection_selectors = DETECTION_SELECTORS
    detection.utils = ActionUtils()
    detection.logger = logger
    strategy = ListScrapingStrategy(get_visible=detection.get_visible_followers_with_elements,
                                    is_on_list=lambda: True, scroll_down=lambda: None,
                                    enable_suggestions_check=False)
    scraper = _Scraper(phone, visits=3)

    scraped = scraper._scrape_list(3, "FOLLOWER", "demo", enrich_on_the_fly=True, strategy=strategy)

    assert scraped == []
    assert scraper.visits == [("alpha_demo", "alpha_demo"), ("bravo_demo", "bravo_demo"),
                              ("charlie_demo", "charlie_demo")]


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
