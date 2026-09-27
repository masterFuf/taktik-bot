"""`scroll_to_next_video` reads the screen again and says whether the video changed.

It answered True after every swipe. On a Pixel 6a (TikTok 47.0.3) a controlled drag of the For
You pager turns the page from about 0.40 of the screen and snaps back under it (0 in 18 at
0.33-0.38, 20 in 20 from 0.50); the production feed drag, whose travel the sampler used to cut
short, snapped back 2 times in 20. A snapped-back pager is swiped once more, then reported.

The screens are real captures, anonymized: a For You video of the base version (43.1.4), and a
video of 46.9.3 as the next one, read by the production readers.
"""

from pathlib import Path

import pytest
from loguru import logger
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.device.snapshot as snapshot_module
import taktik.core.social_media.tiktok.actions.atomic.scroll.scroll_actions as scroll_module
from taktik.core.social_media.tiktok.actions.atomic.scroll.scroll_actions import ScrollActions
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale

FIXTURES = Path(__file__).parent.parent / "fixtures"
VIDEO = (FIXTURES / "tt4314_fr_for_you_video.xml").read_text(encoding="utf-8")
NEXT_VIDEO = (FIXTURES / "tt4693_fr_search_result_video.xml").read_text(encoding="utf-8")
# The home screen of the base version shows no author, count or caption the readers know.
NO_IDENTITY = (FIXTURES / "tt4314_fr_home.xml").read_text(encoding="utf-8")


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    monotonic = perf_counter = time

    def sleep(self, seconds):
        self.now += max(float(seconds), 0.0)


class _Phone:
    """Shows `screens[k]` after the k-th swipe (the last one from then on)."""

    wait_timeout = 1.0

    def __init__(self, clock, screens):
        self.clock, self.screens, self.swipes = clock, screens, 0
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        self.clock.now += 0.25
        return self.screens[min(self.swipes, len(self.screens) - 1)]

    def window_size(self):
        return 1080, 2400


@pytest.fixture
def clock(monkeypatch):
    fake = _Clock()
    monkeypatch.setattr(snapshot_module, "time", fake)
    monkeypatch.setattr(scroll_module, "time", fake)
    return fake


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _scroll(clock, screens):
    phone = _Phone(clock, screens)
    scroll = ScrollActions(phone)

    def swipe():
        phone.swipes += 1

    scroll._swipe_to_next_video = swipe
    return scroll, phone


def test_a_swipe_that_turns_the_page_is_reported(clock):
    scroll, phone = _scroll(clock, [VIDEO, NEXT_VIDEO])
    assert scroll.scroll_to_next_video() is True
    assert phone.swipes == 1


def test_a_pager_that_snapped_back_is_swiped_once_more(clock):
    scroll, phone = _scroll(clock, [VIDEO, VIDEO, NEXT_VIDEO])
    assert scroll.scroll_to_next_video() is True
    assert phone.swipes == 2


def test_the_same_video_after_every_attempt_is_a_failure(clock):
    scroll, phone = _scroll(clock, [VIDEO])
    assert scroll.scroll_to_next_video() is False
    assert phone.swipes == ScrollActions.NEXT_VIDEO_ATTEMPTS


def test_a_screen_without_identity_is_swiped_once_and_said_unverified(clock):
    messages = []
    sink = logger.add(lambda m: messages.append(m.record["message"]), level="DEBUG")
    try:
        scroll, phone = _scroll(clock, [NO_IDENTITY, VIDEO])
        assert scroll.scroll_to_next_video() is True
    finally:
        logger.remove(sink)
    assert phone.swipes == 1
    assert any("not verified" in message for message in messages)
