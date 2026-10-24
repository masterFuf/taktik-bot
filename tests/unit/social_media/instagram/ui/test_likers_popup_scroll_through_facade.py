"""The likers popup scrolls whichever device the reader was built on: the run's or the Lab's facade.

Measured on a Pixel 6 Pro (Instagram 410, Android 17, in French), Lab action `post.read_likers`:
"Error scrolling popup: BaseDeviceFacade.swipe() got an unexpected keyword argument 'duration'",
then "0 liker(s)". The reader called `swipe(x1, y1, x2, y2, duration=0.5)`, the signature of the raw
uiautomator2 device a run hands it; the Lab hands the shared facade, whose `swipe` takes a
direction. Every scroll raised, the popup was taken for closed, and the reading stopped empty.

The screen is a real dump, anonymized: the likers sheet of a post (Instagram 410 in French, Pixel 3a).
The phone answers `xpath` from it and records the path a gesture injects.
"""

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.instagram.ui.extractors as extractors
from taktik.core.shared.device.facade import BaseDeviceFacade
from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors
from unit.paths import CORE

LIKERS_SHEET = (CORE / "tests/unit/social_media/instagram/fixtures/ig410_fr_likers_sheet.xml").read_text(
    encoding="utf-8"
)
WIDTH, HEIGHT = 1080, 2220


class _Phone:
    """A raw uiautomator2 device as far as the reader and the gesture read it."""

    wait_timeout = 0.0

    def __init__(self):
        self.xpath = XPathEntry(self)
        self.paths = []

    def dump_hierarchy(self, *_a, **_k):
        return LIKERS_SHEET

    @property
    def info(self):
        return {"displayWidth": WIDTH, "displayHeight": HEIGHT}

    def window_size(self):
        return WIDTH, HEIGHT

    def swipe_points(self, points, _duration):
        self.paths.append([tuple(point) for point in points])

    def swipe(self, x1, y1, x2, y2, duration=0.5):
        self.paths.append([(x1, y1), (x2, y2)])


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch):
    monkeypatch.setattr(extractors.time, "sleep", lambda *_: None)


@pytest.mark.parametrize("hold", ["facade", "raw"], ids=["lab-facade", "run-raw-device"])
def test_the_popup_scrolls_up_on_the_facade_and_on_the_raw_device(hold):
    phone = _Phone()
    device = BaseDeviceFacade(phone) if hold == "facade" else phone

    assert InstagramUIExtractors(device).scroll_likers_popup_up(verbose_logs=False) is True

    # One gesture, finger moving up the sheet: the next likers come up from below.
    assert len(phone.paths) == 1
    (start_x, start_y), (end_x, end_y) = phone.paths[0][0], phone.paths[0][-1]
    assert end_y < start_y
    assert 0 < start_x < WIDTH and 0 < end_x < WIDTH
