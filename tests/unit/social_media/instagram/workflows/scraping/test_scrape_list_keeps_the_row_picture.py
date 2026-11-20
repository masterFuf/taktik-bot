"""A scrape that opens no profile keeps the picture each row shows, from one screenshot per screen.

Before 2026-11-21 the non-enriched scrape emitted `profile_captured` without a picture: the
Activity showed initials for every account it collected (remark of 2026-10-29). The row's picture
is now cropped from a screenshot of the list, one for the screen however many rows it keeps, and
goes the way the visited profile's goes (`profile_pic_base64`, a JPEG data URL). It never replaces a
picture already kept for the profile (`profile_has_picture`): a row's is smaller, and a row whose
picture has not loaded shows a grey silhouette.

The screen is a real followers list of Instagram 410.0.0.53.71 in French (Pixel 3), anonymized,
behind the facade production mounts; the screenshot is an image of its size.
"""

import pytest
from PIL import Image

from taktik.core.social_media.instagram.actions.base.ipc import IPCEmitter
from taktik.core.social_media.instagram.workflows.scraping import list_scraping
from test_scrape_list_row_tap import LIST, _Phone, _Scraper, _followers_strategy


class _ScreenshotPhone(_Phone):
    def __init__(self, xml):
        super().__init__(xml)
        self.screenshots = 0

    def screenshot(self):
        self.screenshots += 1
        return Image.new("RGB", (1080, 2160), (200, 120, 40))


@pytest.fixture
def captured():
    lines = []
    IPCEmitter.configure_bridge_adapter(type("Bridge", (), {
        "send_profile_captured": staticmethod(
            lambda username, profile_data=None, profile_pic_base64=None: lines.append((username, profile_pic_base64))),
    })())
    yield lines
    IPCEmitter.clear_bridge_adapter()


class _Base:
    """The base as the scrape asks it: which profiles already have a picture kept."""

    def __init__(self, pictured=()):
        self.pictured = set(pictured)

    def profile_has_picture(self, username):
        return username in self.pictured


def _scrape(enrich, monkeypatch, pictured=()):
    monkeypatch.setattr(list_scraping.time, "sleep", lambda *_: None)
    phone = _ScreenshotPhone(LIST)
    scraper = _Scraper(phone)
    base = _Base(pictured)
    scraper._local_db = lambda: base
    scraped = scraper._scrape_list(3, "FOLLOWER", "demo", enrich_on_the_fly=enrich,
                                   strategy=_followers_strategy(phone))
    return phone, scraped


def test_each_row_kept_goes_with_its_picture_from_one_screenshot(monkeypatch, captured):
    phone, scraped = _scrape(False, monkeypatch)

    assert len(scraped) == 3 and [name for name, _ in captured] == [p["username"] for p in scraped]
    assert all(picture and picture.startswith("data:image/jpeg;base64,") for _, picture in captured)
    assert phone.screenshots == 1


def test_an_enriched_scrape_takes_no_list_screenshot(monkeypatch, captured):
    phone, _scraped = _scrape(True, monkeypatch)

    assert phone.screenshots == 0


def test_a_picture_already_kept_is_not_replaced_by_the_row(monkeypatch, captured):
    _phone, scraped = _scrape(False, monkeypatch)
    pictured = scraped[0]["username"]
    captured.clear()

    _scrape(False, monkeypatch, pictured=[pictured])

    by_name = dict(captured)
    assert by_name[pictured] is None
    assert all(picture for name, picture in captured if name != pictured)
