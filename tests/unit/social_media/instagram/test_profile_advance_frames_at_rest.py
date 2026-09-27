"""After an advance in a profile's post list, the framing is decided on the list at rest, from the
top of the list.

Measured on a Pixel 6a (Instagram 447 in French, a public profile, 10 advances): the landing was
read about half a second after the flick, while the list still coasted; the correction computed
from that reading was applied to a list that had moved on, and 7 of the 10 advances ended with the
first header between 38 % and 89 % of the screen, the post above still filling the top. And the
correction aimed at a ratio of the SCREEN (3 to 9 %), while this list starts under a fixed title bar
(11.6 % of the screen): a landing measured right still pushed the header under that bar.

The screen is a real dump, anonymized (`ig447_fr_profile_posts_next_header_mid_screen.xml`): the
list at rest after an advance, the previous post's photo, buttons and caption at the top, the next
post's header at 38 %, its photo and its button row below. `profile_posts_phone.py` replays it,
and after the flick lets the list coast on the curve measured on the same phone (still 18.7 % of the
screen to travel 0.1 s after the flick, 4.5 % after 0.34 s, at rest after 0.74 s). A dump costs
0.12 s, as it did there.
"""

import pytest
from loguru import logger

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll as feed_scroll
import taktik.core.social_media.instagram.actions.business.actions.like.post_navigation as post_navigation
import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
from profile_posts_phone import PKG, ProfilePostsPhone, ReplayGestures, bounds_of, capture
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.behavior.session_state import BehaviorSessionState
from taktik.core.social_media.instagram.actions.atomic.scroll.base_scroll import BaseScrollMixin
from taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll import FeedScrollMixin
from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
    LikeOrchestration,
)
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_SELECTORS

AT_REST = capture("ig447_fr_profile_posts_next_header_mid_screen.xml")
DUMP_S = 0.12
#: Px the list still had to travel so many seconds after the flick returned (Pixel 6a, IG 447).
MEASURED_COAST = [(0.0, 615), (0.10, 449), (0.23, 233), (0.34, 108), (0.46, 22), (0.60, 2),
                  (0.74, 0)]
GOOD = 0.12


class _Scroll(ReplayGestures, FeedScrollMixin):
    """The scroll owner (`ScrollActions` in production) on the replayed phone. The advance is a
    flick; the framing policy is the plain one (no session memory), so every correction is made."""

    screen_width = 1080

    def __init__(self, phone, device):
        self.screen_height = phone.height
        self.phone = phone
        self.device = device
        self.logger = logger.bind(module="test_profile_advance_frames_at_rest")
        self.gestures = []

    def _choose_advance_mode(self, context, base_drag_probability=0.15):
        return {"context": context, "mode": "flick", "style": None, "burst_remaining": 0,
                "distance_scale": 1.0, "velocity_scale": 1.0, "settle_scale": 1.0}

    def _strong_flick(self, direction="up", distance_px=None, **_kwargs):
        self.gestures.append(("flick", direction, int(distance_px)))
        self.phone.coast_to_rest(0, MEASURED_COAST)
        return True


@pytest.fixture(autouse=True)
def _french_phone(monkeypatch):
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _phone_and_scroll(monkeypatch):
    phone = ProfilePostsPhone(screen=AT_REST, dump_s=DUMP_S)
    for module in (feed_scroll, post_navigation, facade_module, shared_facade_module):
        monkeypatch.setattr(module.time, "sleep", phone.sleep)
    for module in (feed_scroll, post_navigation):
        monkeypatch.setattr(module.random, "uniform", lambda low, _high: low)
    device = DeviceFacade(CloneAwareDeviceProxy(phone, PKG))
    return phone, _Scroll(phone, device)


def _headers_on_screen(phone):
    """(top, description) of every post header the phone shows now, and the top of the list."""
    from lxml import etree

    root = etree.fromstring(phone.dump_hierarchy().encode("utf-8"))
    list_top = next(bounds_of(n)[1] for n in root.iter() if n.get("resource-id") == "android:id/list")
    headers = [(bounds_of(n)[1], n.get("content-desc")) for n in root.iter()
               if n.get("resource-id") == f"{PKG}:id/row_feed_profile_header"]
    return sorted(headers), list_top


def _assert_framed_below_the_title_bar(phone, identity):
    headers, list_top = _headers_on_screen(phone)
    tops = [top for top, desc in headers if desc == identity]
    assert tops, f"the post the list stopped on left the screen (headers: {headers})"
    top = tops[0]
    assert top > list_top, (
        f"its header is under the title bar ({top} px, the list starts at {list_top} px)")
    assert top - list_top <= GOOD * phone.height, (
        f"its header sits {100 * (top - list_top) / phone.height:.0f} % of the screen below the "
        f"top of the list: the post above still fills the top")


def test_the_advance_frames_the_post_the_list_stopped_on(monkeypatch):
    phone, scroll = _phone_and_scroll(monkeypatch)
    identity = scroll.framed_post_identity()
    host = object.__new__(LikeOrchestration)
    host.device = scroll.device
    host.logger = scroll.logger
    host.scroll_actions = scroll
    host.post_selectors = POST_SELECTORS

    assert host._navigate_to_next_post_in_sequence() is True

    _assert_framed_below_the_title_bar(phone, identity)
    assert scroll.framed_post_identity() == identity


def test_a_correction_measured_at_rest_keeps_the_header_below_the_title_bar(monkeypatch):
    phone, scroll = _phone_and_scroll(monkeypatch)
    identity = scroll.framed_post_identity()

    result = scroll.land_on_post_header()

    _assert_framed_below_the_title_bar(phone, identity)
    assert result["framed"] is True
    assert result["corrected"] is True


@pytest.mark.parametrize("seed", range(12))
def test_a_header_a_quarter_of_the_screen_down_the_list_is_always_brought_up(monkeypatch, seed):
    # The session policy accepts a small imperfection now and then, never a post that leaves the
    # previous one a quarter of the screen: the header here sits 26 % of the screen below the top
    # of the list (38 % of the screen from its top).
    phone, scroll = _phone_and_scroll(monkeypatch)
    identity = scroll.framed_post_identity()
    scroll.behavior_state = BehaviorSessionState(seed=seed)
    scroll._decide_post_framing = BaseScrollMixin._decide_post_framing.__get__(scroll)

    result = scroll.land_on_post_header()

    assert result["framing_decision"]["reason"] == "critical_misalignment"
    _assert_framed_below_the_title_bar(phone, identity)
