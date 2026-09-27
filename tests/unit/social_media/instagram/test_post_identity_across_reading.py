"""Reading a post's description must not make the like guard lose the post, nor lose track of it.

Run case (Instagram, likes on the posts of a visited profile): "Frame drifted after reading the
description" three times in five minutes. The guard compares the post's identity before and after
the reading (caption expanded, scrolled into view, then scrolled back) and drops the like when they
differ. Two things made it wrong:

- the identity was read from the whole screen: the Reel flag was true as soon as ANY "Reel de ..."
  label was on screen, and the counters came from the first label found, falling back to the
  numbers of the button row. On the screen below, the framed post is a carousel and the next
  post's Reel peeks at the bottom: before the reading the identity was the NEXT post's
  (its likes, its comments, a Reel); once the frame came back a little lower, that Reel had left
  the screen and the identity became the framed post's own (from its buttons, not a Reel). Same
  post, two identities: the like was dropped. And a post really left behind could keep the same
  borrowed identity, so a real drift could pass;
- the way back was an estimate: the distance the drags asked for, times a random 0.95-1.15
  (544 px read, 607 back; 1052 read, 1201 back), never checked against the screen.

The screen is a real dump, anonymized: the posts of a profile opened from its grid, Instagram 447
in French on a Pixel 6a (1080x2400). The phone (`profile_posts_phone.py`) replays it scrolled by
the distance the gestures really travel (the list content moves, the bars stay), each gesture
losing the touch slop before the content follows the finger.
"""

import pytest
from loguru import logger

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as post_reading
import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
from profile_posts_phone import PKG, SCREEN_H, ProfilePostsPhone, ReplayGestures, capture
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
from taktik.core.social_media.instagram.actions.atomic.scroll.post_reading import PostReadingMixin
from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
    LikeOrchestration,
)
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

#: Home feed, Instagram 410 in French, Pixel 3a (1080x2220): the previous post's truncated
#: caption still at the top, the framed post's own caption a sliver above the tab bar.
PREVIOUS_CAPTION_ABOVE = capture("ig410_fr_feed_previous_caption_above_header.xml")
#: The run's second case: the reading asked for 1052 px, the way back for 1201 px (x 1.1416).
RUN_BACK_BIAS = 1201 / 1052


class _Reader(ReplayGestures, PostReadingMixin):
    """The reading owner (`ScrollActions` in production), its gestures moving the phone."""

    screen_width = 1080

    def __init__(self, phone, device):
        self.screen_height = phone.height
        self.phone = phone
        self.device = device
        self.logger = logger.bind(module="test_post_identity_across_reading")
        self.gestures = []


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, post_reading):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _host(phone):
    device = DeviceFacade(CloneAwareDeviceProxy(phone, PKG))
    host = object.__new__(LikeOrchestration)
    host.device = device
    host.logger = logger.bind(module="test_post_identity_across_reading")
    host.detection_actions = DetectionActions(device)
    host.ui_extractors = InstagramUIExtractors(device)
    host.scroll_actions = _Reader(phone, device)
    host.likes = []
    host.like_current_post = lambda: host.likes.append(phone.offset) or True
    host._stop_if_action_blocked = lambda *_args: False
    return host


def _a_reading_that_expands_the_caption(monkeypatch):
    """The reading as the run drew it: the caption is expanded, one reveal drag of 0.30 screen,
    no dwell, and the way back asks for the run's 1.14 x the reveal."""
    def uniform(lower, upper):
        if (lower, upper) == (0.95, 1.15):
            return RUN_BACK_BIAS
        if (lower, upper) == (0.20, 0.30):
            return upper
        return lower

    monkeypatch.setattr(post_reading.random, "random", lambda: 0.0)
    monkeypatch.setattr(post_reading.random, "uniform", uniform)
    monkeypatch.setattr(post_reading.random, "randint", lambda lower, _upper: lower)
    monkeypatch.setattr(post_reading, "content_dwell", lambda _prose: 0.0)


def test_the_identity_of_the_framed_post_does_not_depend_on_its_neighbour():
    phone = ProfilePostsPhone()
    host = _host(phone)

    with_next_reel_peeking = host._current_post_signature()
    phone.offset = -120  # the same post, framed 120 px lower: the next Reel leaves the screen
    without_it = host._current_post_signature()

    assert with_next_reel_peeking == without_it


def test_a_post_read_and_brought_back_keeps_its_like(monkeypatch):
    _a_reading_that_expands_the_caption(monkeypatch)
    phone = ProfilePostsPhone()
    host = _host(phone)

    liked, _commented = host._run_engagement_sequence(["read", "like"], "profil_exemple", [], {})

    assert liked is True, "the guard dropped the like of the post it had just read"
    assert host.likes == [phone.offset]


def test_the_read_post_is_brought_back_where_it_was_as_the_screen_shows(monkeypatch):
    _a_reading_that_expands_the_caption(monkeypatch)
    phone = ProfilePostsPhone()
    reader = _host(phone).scroll_actions

    reader.human_reading_pause()

    revealed = [g for g in reader.gestures if g[:2] == ("drag", "up")]
    assert revealed, "the reading must have scrolled the expanded caption into view"
    # Back where it was, as the screen shows it, not as the drags' arithmetic hopes.
    assert abs(phone.offset) <= 0.03 * SCREEN_H, f"left {phone.offset} px off after reading"
    assert reader.last_reading_reframed is True


def test_a_way_back_that_coasts_past_the_post_is_caught_by_its_header(monkeypatch):
    # Measured on a Pixel 6a (Instagram 447): the list went on after the swipe back and the read
    # post ended far below where it sat, its caption off the screen, its header still on it.
    _a_reading_that_expands_the_caption(monkeypatch)
    phone = ProfilePostsPhone(back_swipe_coast=2.5)
    reader = _host(phone).scroll_actions

    reader.human_reading_pause()

    assert abs(phone.offset) <= 0.03 * SCREEN_H, f"left {phone.offset} px off after reading"
    assert reader.last_reading_reframed is True


def test_a_post_left_behind_is_still_caught_and_not_liked(monkeypatch):
    # The screen does not follow the way back: the reading leaves the next post framed.
    _a_reading_that_expands_the_caption(monkeypatch)
    phone = ProfilePostsPhone(obeys_back_swipes=False)
    host = _host(phone)

    liked, _commented = host._run_engagement_sequence(["read", "like"], "profil_exemple", [], {})

    assert liked is False
    assert host.likes == [], "a like landed on a screen that no longer frames the read post"
    assert host.scroll_actions.last_reading_reframed is False


def test_the_visit_tells_the_framed_post_by_its_own_header_and_counters():
    phone = ProfilePostsPhone()
    reader = _host(phone).scroll_actions

    header, counters = reader.framed_post_signature().split(" | ")

    assert header == reader.framed_post_identity()
    assert " a publié " in header
    # The counters of its own button row, never the next Reel's label (20 144 likes, 44 comments).
    assert counters.split(" ") == ["1 781", "38", "14", "23"]


def test_the_reading_never_opens_the_previous_posts_caption(monkeypatch):
    # The previous post's caption is the taller one on screen, with its expander in full view; the
    # framed post's own expander runs under the tab bar. Neither may be tapped.
    _a_reading_that_expands_the_caption(monkeypatch)
    phone = ProfilePostsPhone(screen=PREVIOUS_CAPTION_ABOVE, height=2220)
    reader = _host(phone).scroll_actions

    assert reader.expand_caption_if_truncated() is False
    assert phone.taps == []
