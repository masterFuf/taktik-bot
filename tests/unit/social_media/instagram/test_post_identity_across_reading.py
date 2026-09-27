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
in French on a Pixel 6a (1080x2400). The phone below replays it scrolled by the distance the
gestures really travel (the list content moves, the bars stay), each gesture losing the touch slop
before the content follows the finger.
"""

from pathlib import Path

import pytest
from loguru import logger
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as post_reading
import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
from taktik.core.social_media.instagram.actions.atomic.scroll.post_reading import PostReadingMixin
from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
    LikeOrchestration,
)
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

PKG = "com.instagram.android"
FIXTURES = Path(__file__).parent / "fixtures"
PROFILE_POSTS = (FIXTURES / "ig447_fr_profile_posts_list.xml").read_text(encoding="utf-8")
SCREEN_W, SCREEN_H = 1080, 2400
LIST_ID = "android:id/list"
#: Touch slop of a 2.75-density screen: what a gesture travels before the content follows.
TOUCH_SLOP_PX = 22
#: The run's second case: the reading asked for 1052 px, the way back for 1201 px (x 1.1416).
RUN_BACK_BIAS = 1201 / 1052


def _bounds(node):
    left_top, right_bottom = node.get("bounds").strip("[]").split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


def _scrolled(xml: str, offset: int) -> str:
    """The captured screen with its list content moved UP by `offset` px (down when negative).

    Nodes inside the list move and are clipped to it, as uiautomator reports them; a node that
    leaves the list is gone. Nothing outside the list moves. Content that was off the capture
    stays unknown: what scrolls in shows as empty list."""
    root = etree.fromstring(xml.encode("utf-8"))
    lists = [node for node in root.iter() if node.get("resource-id") == LIST_ID]
    if not lists or not offset:
        return xml
    list_node = lists[0]
    _left, list_top, _right, list_bottom = _bounds(list_node)
    for node in list(list_node.iter()):
        if node is list_node or node.get("bounds") is None:
            continue
        left, top, right, bottom = _bounds(node)
        top, bottom = top - offset, bottom - offset
        if bottom <= list_top or top >= list_bottom:
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
            continue
        node.set("bounds", f"[{left},{max(top, list_top)}][{right},{min(bottom, list_bottom)}]")
    return etree.tostring(root, encoding="unicode")


class _ProfilePostsPhone:
    """uiautomator2 behind the proxy and the facade, replaying the capture at a scroll offset."""

    wait_timeout = 1.0
    info = {"displayWidth": SCREEN_W, "displayHeight": SCREEN_H}

    def __init__(self, obeys_back_swipes=True):
        self.offset = 0
        self.obeys_back_swipes = obeys_back_swipes
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return _scrolled(PROFILE_POSTS, self.offset)

    def app_current(self):
        return {"package": PKG}

    def window_size(self):
        return SCREEN_W, SCREEN_H

    def click(self, x, y):
        self.taps.append((x, y))

    def press(self, key, meta=None):
        return True

    # The content follows the finger once the touch slop is crossed.
    def drag_content_up(self, distance_px):
        self.offset += max(0, int(distance_px) - TOUCH_SLOP_PX)

    def drag_content_down(self, distance_px):
        if self.obeys_back_swipes:
            self.offset -= max(0, int(distance_px) - TOUCH_SLOP_PX)


class _Reader(PostReadingMixin):
    """The reading owner (`ScrollActions` in production), its gestures moving the phone."""

    screen_width = SCREEN_W
    screen_height = SCREEN_H

    def __init__(self, phone, device):
        self.phone = phone
        self.device = device
        self.logger = logger.bind(module="test_post_identity_across_reading")
        self.gestures = []

    def _long_drag(self, direction="up", distance_px=None, **_kwargs):
        self.gestures.append(("drag", direction, int(distance_px)))
        if direction == "up":
            self.phone.drag_content_up(distance_px)
        else:
            self.phone.drag_content_down(distance_px)
        return True

    def _human_swipe(self, direction="up", distance_px=None, **_kwargs):
        self.gestures.append(("swipe", direction, int(distance_px)))
        if direction == "down":
            self.phone.drag_content_down(distance_px)
        else:
            self.phone.drag_content_up(distance_px)
        return True

    def _human_horizontal_swipe(self, *_args, **_kwargs):
        self.gestures.append(("hswipe",))
        return True


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
    phone = _ProfilePostsPhone()
    host = _host(phone)

    with_next_reel_peeking = host._current_post_signature()
    phone.offset = -120  # the same post, framed 120 px lower: the next Reel leaves the screen
    without_it = host._current_post_signature()

    assert with_next_reel_peeking == without_it


def test_a_post_read_and_brought_back_keeps_its_like(monkeypatch):
    _a_reading_that_expands_the_caption(monkeypatch)
    phone = _ProfilePostsPhone()
    host = _host(phone)

    liked, _commented = host._run_engagement_sequence(["read", "like"], "profil_exemple", [], {})

    assert liked is True, "the guard dropped the like of the post it had just read"
    assert host.likes == [phone.offset]


def test_the_read_post_is_brought_back_where_it_was_as_the_screen_shows(monkeypatch):
    _a_reading_that_expands_the_caption(monkeypatch)
    phone = _ProfilePostsPhone()
    reader = _host(phone).scroll_actions

    reader.human_reading_pause()

    revealed = [g for g in reader.gestures if g[:2] == ("drag", "up")]
    assert revealed, "the reading must have scrolled the expanded caption into view"
    # Back where it was, as the screen shows it, not as the drags' arithmetic hopes.
    assert abs(phone.offset) <= 0.03 * SCREEN_H, f"left {phone.offset} px off after reading"
    assert reader.last_reading_reframed is True


def test_a_post_left_behind_is_still_caught_and_not_liked(monkeypatch):
    # The screen does not follow the way back: the reading leaves the next post framed.
    _a_reading_that_expands_the_caption(monkeypatch)
    phone = _ProfilePostsPhone(obeys_back_swipes=False)
    host = _host(phone)

    liked, _commented = host._run_engagement_sequence(["read", "like"], "profil_exemple", [], {})

    assert liked is False
    assert host.likes == [], "a like landed on a screen that no longer frames the read post"
    assert host.scroll_actions.last_reading_reframed is False


def test_the_visit_tells_the_framed_post_by_its_own_header_and_counters():
    phone = _ProfilePostsPhone()
    reader = _host(phone).scroll_actions

    header, counters = reader.framed_post_signature().split(" | ")

    assert header == reader.framed_post_identity()
    assert " a publié " in header
    # The counters of its own button row, never the next Reel's label (20 144 likes, 44 comments).
    assert counters.split(" ") == ["1 781", "38", "14", "23"]
