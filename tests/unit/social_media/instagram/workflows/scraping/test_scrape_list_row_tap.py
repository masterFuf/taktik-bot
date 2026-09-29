"""The enriching scrape taps a row read on a photo of the screen.

The rows come from `get_visible_followers_with_elements`, which reads one photo of the screen:
its elements carry text and bounds but no device, so `.click()` on them raises. The old fallback
`element.click()` behind the human tap therefore raised, and the scrape's error path pressed
back from the list it had never left. Now a row that could not be tapped is kept without its
details and nothing else moves.

The phone is uiautomator2's own xpath engine behind the facade production mounts
(`CloneAwareDeviceProxy`). Its screen is a real followers list of Instagram 410.0.0.53.71 in
French (Pixel 3), anonymized; the untappable row is the same screen with its first name given
no size (derived).
"""

from lxml import etree
from loguru import logger
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.ui_dump import parse_bounds
from taktik.core.social_media.instagram.actions.atomic.detection.list_detection import (
    ListDetectionMixin,
)
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.actions.core.utils import ActionUtils
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.workflows.scraping.list_scraping import ScrapingListMixin
from taktik.core.social_media.instagram.workflows.scraping.list_strategy import ListScrapingStrategy
from unit.paths import CORE

PKG = "com.instagram.android"
LIST = (CORE / "tests/unit/social_media/instagram/fixtures/ig410_fr_followers_list_top.xml").read_text(encoding="utf-8")


def _first_name(root):
    return next(n for n in root.iter("node") if n.get("resource-id", "").endswith("/follow_list_username"))


FIRST = _first_name(etree.fromstring(LIST.encode("utf-8")))
FIRST_NAME, FIRST_BOUNDS = FIRST.get("text"), parse_bounds(FIRST.get("bounds"))


def _without_size():
    root = etree.fromstring(LIST.encode("utf-8"))
    _first_name(root).set("bounds", "[0,0][0,0]")
    return etree.tostring(root, encoding="unicode")


class _Phone:
    """The raw device the scrape holds, and what uiautomator2's `d.xpath()` needs."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2160}

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
        return 1080, 2160


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


def _scrape(xml):
    phone = _Phone(xml)
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
    scraper, phone, scraped = _scrape(LIST)
    assert [profile["username"] for profile in scraped] == [FIRST_NAME]
    assert len(phone.taps) == 1
    x, y = phone.taps[0]
    left, top, right, bottom = FIRST_BOUNDS
    assert left <= x <= right and top <= y <= bottom
    assert scraper.captured == [FIRST_NAME] and scraper.backs_to_list == 1
    assert phone.presses == []


def test_a_row_that_cannot_be_tapped_is_kept_and_the_list_is_not_left():
    scraper, phone, scraped = _scrape(_without_size())
    assert [profile["username"] for profile in scraped] == [FIRST_NAME]
    assert phone.taps == [] and scraper.captured == [] and scraper.backs_to_list == 0
    assert phone.presses == []
