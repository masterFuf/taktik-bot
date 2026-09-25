"""The enriching scrape taps a row read on a photo of the screen.

The rows come from `get_visible_followers_with_elements`, which reads one photo of the screen:
its elements carry text and bounds but no device, so `.click()` on them raises. The old fallback
`element.click()` behind the human tap therefore raised, and the scrape's error path pressed
back from the list it had never left. Now a row that could not be tapped is kept without its
details and nothing else moves.

The phone is uiautomator2's own xpath engine behind the facade production mounts
(`CloneAwareDeviceProxy`); the dumps are invented (public repository).
"""

from loguru import logger
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.atomic.detection.list_detection import (
    ListDetectionMixin,
)
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.actions.core.utils import ActionUtils
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.workflows.scraping.list_scraping import ScrapingListMixin
from taktik.core.social_media.instagram.workflows.scraping.list_strategy import ListScrapingStrategy

PKG = "com.instagram.android"


def _screen(bounds):
    left, top, right, bottom = bounds
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            f'<node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="{PKG}" '
            'bounds="[0,0][1080,2400]">'
            f'<node index="0" text="bob_demo" resource-id="{PKG}:id/follow_list_username" '
            f'class="android.widget.TextView" package="{PKG}" content-desc="" clickable="true" '
            f'enabled="true" bounds="[{left},{top}][{right},{bottom}]" />'
            '</node></hierarchy>')


class _Phone:
    """The raw device the scrape holds, and what uiautomator2's `d.xpath()` needs."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2400}

    def __init__(self, xml):
        self.xml = xml
        self.taps = []
        self.presses = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def click(self, x, y):
        self.taps.append((x, y))

    def long_click(self, x, y, _duration=0.0):
        self.taps.append((x, y))

    def press(self, key):
        self.presses.append(key)

    def window_size(self):
        return 1080, 2400


class _Scraper(ScrapingListMixin):
    def __init__(self, phone):
        self.device = phone
        self.logger = logger
        self.config = {"rescrape_after_days": 0}
        self.scraped_profiles = []
        self.captured = []
        self.backs_to_list = 0

    def _should_continue(self):
        return True

    def _capture_profile_on_screen(self, username, **_kwargs):
        self.captured.append(username)
        return None

    def _back_to_list(self, _strategy):
        self.backs_to_list += 1

    def _save_profile_immediately(self, _profile, source_post_url=None):
        return None


def _scrape(bounds):
    phone = _Phone(_screen(bounds))
    detection = object.__new__(ListDetectionMixin)
    detection.device = DeviceFacade(CloneAwareDeviceProxy(phone, PKG))
    detection.detection_selectors = DETECTION_SELECTORS
    detection.utils = ActionUtils()
    detection.logger = logger
    strategy = ListScrapingStrategy(get_visible=detection.get_visible_followers_with_elements,
                                    is_on_list=lambda: True, scroll_down=lambda: None,
                                    enable_suggestions_check=False)
    scraper = _Scraper(phone)
    scraped = scraper._scrape_list(1, "FOLLOWER", "demo", enrich_on_the_fly=True, strategy=strategy)
    return scraper, phone, scraped


def test_a_row_is_tapped_inside_its_bounds_and_enriched():
    scraper, phone, scraped = _scrape((200, 600, 700, 650))
    assert [profile["username"] for profile in scraped] == ["bob_demo"]
    assert len(phone.taps) == 1
    x, y = phone.taps[0]
    assert 200 <= x <= 700 and 600 <= y <= 650
    assert scraper.captured == ["bob_demo"] and scraper.backs_to_list == 1
    assert phone.presses == []


def test_a_row_that_cannot_be_tapped_is_kept_and_the_list_is_not_left():
    scraper, phone, scraped = _scrape((0, 0, 0, 0))
    assert [profile["username"] for profile in scraped] == ["bob_demo"]
    assert phone.taps == [] and scraper.captured == [] and scraper.backs_to_list == 0
    assert phone.presses == []
