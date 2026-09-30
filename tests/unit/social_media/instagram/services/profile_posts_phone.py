"""A phone that replays a real capture of a list of posts (a profile's, the home feed), for the tests
that move it.

The screen is a real dump, anonymized (Instagram 447 in French on a Pixel 6a, 1080x2400, unless a
test hands another). The list content moves by the distance the gestures really travel, the bars
stay; each gesture loses the touch slop before the content follows the finger. A flick can leave
the list coasting on its measured curve: it goes on moving until it comes to rest, or until a
finger touches it down. A tap or a double tap on a post can like it, as Instagram does: its heart
turns selected. Nothing here writes a screen: every tree is the capture, moved.

`like_on_phone` builds the production like of a list (`LikeOrchestration`) on such a phone, with
the production scroll owner's readers and drags (`ReplayScroll`).
"""

from loguru import logger
from lxml import etree
from uiautomator2.xpath import XPathEntry

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.behavior.gesture import SWIPE_FLOOR_H
from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
from taktik.core.social_media.instagram.actions.atomic.interaction import ClickActions
from taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll import FeedScrollMixin
from taktik.core.social_media.instagram.services.like.orchestration import LikeOrchestration
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
SCREEN_W, SCREEN_H = 1080, 2400
LIST_ID = "android:id/list"
HEADER_ID = f"{PKG}:id/row_feed_profile_header"
HEART_ID = f"{PKG}:id/row_feed_button_like"
#: Touch slop of a 2.75-density screen: what a gesture travels before the content follows.
TOUCH_SLOP_PX = 22


def capture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def bounds_of(node):
    left_top, right_bottom = node.get("bounds").strip("[]").split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


def scrolled(xml: str, offset: int) -> str:
    """The captured screen with its list content moved UP by `offset` px (down when negative).

    Nodes inside the list move and are clipped to it, as uiautomator reports them; a node that
    leaves the list is gone. Nothing outside the list moves. Content that was off the capture
    stays unknown: what scrolls in shows as empty list."""
    root = etree.fromstring(xml.encode("utf-8"))
    lists = [node for node in root.iter() if node.get("resource-id") == LIST_ID]
    if not lists or not offset:
        return xml
    list_node = lists[0]
    _left, list_top, _right, list_bottom = bounds_of(list_node)
    for node in list(list_node.iter()):
        if node is list_node or node.get("bounds") is None:
            continue
        left, top, right, bottom = bounds_of(node)
        top, bottom = top - offset, bottom - offset
        if bottom <= list_top or top >= list_bottom:
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
            continue
        node.set("bounds", f"[{left},{max(top, list_top)}][{right},{min(bottom, list_bottom)}]")
    return etree.tostring(root, encoding="unicode")


class ProfilePostsPhone:
    """uiautomator2 behind the proxy and the facade, replaying the capture at a scroll offset.

    `clock` counts the seconds the code under test spends on this phone: its sleeps (when the test
    routes `time.sleep` here) and its dumps (`dump_s` each, what one costs on the phone).

    `further` is a second real capture of the same list, (xml, offset): taken on the phone once its
    content had gone `offset` px further up (the distance its headers moved between the two). What
    the first one holds nothing of, under its bottom, the second shows: it is served, moved the
    same way, once the list is nearer to it than to the first."""

    wait_timeout = 1.0

    def __init__(self, obeys_back_swipes=True, back_swipe_coast=1.0, screen=None,
                 height=SCREEN_H, dump_s=0.0, likes_on_tap=False, further=None):
        self.screen = screen if screen is not None else capture("ig447_fr_profile_posts_list.xml")
        self.further = further
        self.height = height
        self.info = {"displayWidth": SCREEN_W, "displayHeight": height}
        self.offset = 0
        self.obeys_back_swipes = obeys_back_swipes
        #: > 1: the list coasts on after a downward swipe, as measured on the phone.
        self.back_swipe_coast = back_swipe_coast
        self.taps = []
        self.clock = 0.0
        self.dump_s = dump_s
        self.likes_on_tap = likes_on_tap
        #: (clock at the flick, [(seconds after it, px still to travel), ...]) while it coasts.
        self._coast = None
        self._liked_hearts = set()
        self._liked_further_hearts = set()
        self.xpath = XPathEntry(self)

    # --- time and the coast ---

    def sleep(self, seconds):
        self.clock += max(0.0, float(seconds))

    def coast_to_rest(self, rest_offset, curve):
        """A flick has just been released: the list goes on to `rest_offset`, `curve` saying how
        far it still has to travel (px) so many seconds after the finger lifted."""
        self.offset = rest_offset
        self._coast = (self.clock, list(curve))

    def _still_to_travel(self):
        if self._coast is None:
            return 0
        started, curve = self._coast
        elapsed = self.clock - started
        if elapsed >= curve[-1][0]:
            return curve[-1][1]
        for (t0, px0), (t1, px1) in zip(curve, curve[1:]):
            if t0 <= elapsed <= t1:
                return int(round(px0 + (px1 - px0) * (elapsed - t0) / (t1 - t0)))
        return curve[0][1]

    def current_offset(self):
        return self.offset - self._still_to_travel()

    def touch_down(self):
        """A finger on the list stops its coast where it is."""
        self.offset = self.current_offset()
        self._coast = None

    # --- what uiautomator2 answers ---

    def _capture_now(self):
        """(capture, its offset, the hearts liked in it): the capture nearest to where the list is."""
        if self.further is not None:
            further, further_offset = self.further
            if abs(self.current_offset() - further_offset) < abs(self.current_offset()):
                return further, further_offset, self._liked_further_hearts
        return self.screen, 0, self._liked_hearts

    def _screen_now(self):
        screen, _offset, liked = self._capture_now()
        root = etree.fromstring(screen.encode("utf-8"))
        for node in root.iter():
            if node.get("resource-id") == HEART_ID and node.get("bounds") in liked:
                node.set("selected", "true")
        return etree.tostring(root, encoding="unicode")

    def dump_hierarchy(self, *_a, **_k):
        xml = scrolled(self._screen_now(), self.current_offset() - self._capture_now()[1])
        self.clock += self.dump_s
        return xml

    def app_current(self):
        return {"package": PKG}

    def window_size(self):
        return SCREEN_W, self.height

    def click(self, x, y):
        self.taps.append(("tap", x, y))
        self._like_at(x, y, heart_only=True)

    def long_click(self, x, y, duration=0.0):
        self.click(x, y)

    def double_click(self, x, y, duration=0.1):
        self.taps.append(("double_tap", x, y))
        self._like_at(x, y, heart_only=False)

    def press(self, key, meta=None):
        return True

    def _like_at(self, x, y, heart_only):
        """Like the post under the point, as Instagram does: a tap on its heart, or a double tap on
        it. The post of a point is the last header above it in the capture."""
        if not self.likes_on_tap:
            return
        screen, offset, liked = self._capture_now()
        captured_y = y + self.current_offset() - offset
        root = etree.fromstring(screen.encode("utf-8"))
        header_tops = sorted(bounds_of(n)[1] for n in root.iter() if n.get("resource-id") == HEADER_ID)
        hearts = [n for n in root.iter() if n.get("resource-id") == HEART_ID]
        if heart_only:
            hit = [n for n in hearts
                   if bounds_of(n)[0] <= x <= bounds_of(n)[2] and bounds_of(n)[1] <= captured_y <= bounds_of(n)[3]]
            if hit:
                liked.add(hit[0].get("bounds"))
            return
        above = [top for top in header_tops if top <= captured_y]
        start = above[-1] if above else -10 ** 6
        later = [top for top in header_tops if top > start]
        end = later[0] if later else 10 ** 6
        own = [n for n in hearts if start <= bounds_of(n)[1] < end]
        if own:
            liked.add(own[0].get("bounds"))

    # The content follows the finger once the touch slop is crossed.
    def drag_content_up(self, distance_px):
        self.touch_down()
        self.offset += max(0, int(distance_px) - TOUCH_SLOP_PX)

    def drag_content_down(self, distance_px):
        self.touch_down()
        if self.obeys_back_swipes:
            self.offset -= int(max(0, int(distance_px) - TOUCH_SLOP_PX) * self.back_swipe_coast)


class ReplayGestures:
    """The 1:1 gestures of the scroll owner (`ScrollActions` in production), moving the phone.
    The host sets `self.phone` and lists what it did in `self.gestures` (the travel asked). A
    drag never travels less than the swipe floor (`SWIPE_FLOOR_H`), as on the phone: a request
    under it goes that far."""

    phone: ProfilePostsPhone
    gestures: list

    def _long_drag(self, direction="up", distance_px=None, **_kwargs):
        self.gestures.append(("drag", direction, int(distance_px)))
        travel = max(float(distance_px), SWIPE_FLOOR_H * self.phone.height)
        if direction == "up":
            self.phone.drag_content_up(travel)
        else:
            self.phone.drag_content_down(travel)
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


class ReplayScroll(ReplayGestures, FeedScrollMixin):
    """The scroll owner of production (`ScrollActions`) on the replayed phone: its readers of the
    framed post, and its drags (the one that shows a framed post's buttons among them)."""

    screen_width = SCREEN_W

    def __init__(self, phone, device):
        self.screen_height = phone.height
        self.phone = phone
        self.device = device
        self.logger = logger.bind(module="replay_scroll")
        self.gestures = []


def like_on_phone(phone) -> LikeOrchestration:
    """The production like of a list (`LikeOrchestration`) on the replayed phone, behind the clone
    proxy and the facade, its pacing cut. Its likes are filed in `rows` (author, kind, count) and
    `session_actions` (kind, author) instead of the database and the session."""
    device = DeviceFacade(CloneAwareDeviceProxy(phone, PKG))
    like = object.__new__(LikeOrchestration)
    like.device = device
    like.logger = logger.bind(module="like_on_phone")
    like.detection_actions = DetectionActions(device)
    like.click_actions = ClickActions(device)
    like.scroll_actions = ReplayScroll(phone, device)
    like.rows = []
    like.session_actions = []
    like.session_manager = _FiledSession(like.session_actions)
    like._record_action = lambda username, kind, count=1, **_kw: like.rows.append((username, kind, count))
    like._human_like_delay = lambda *_args, **_kwargs: None   # the session's pacing, not tested here
    return like


class _FiledSession:
    def __init__(self, actions):
        self.actions = actions

    def record_action(self, action_type, success=True, source=None):
        self.actions.append((action_type, source))
