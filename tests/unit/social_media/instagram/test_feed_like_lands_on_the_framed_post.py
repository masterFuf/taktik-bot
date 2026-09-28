"""The Feed likes the framed post, the one whose header its guards check, or nothing.

The Feed kept its own like: the first like button of the SCREEN for the button path (and its state
for "already liked"), a fixed band of the screen (30-70 % wide, 30-52 % high) for the double tap. On
a feed the post above often shows its button row at the top: 8 of the 93 real landings of the
Lab corpus whose framed post had its heart on screen (Pixel 3a, Instagram 410 in French, 155
`scroll.feed_next` runs) also showed the heart of the post above, first in the dump; on 36 of the 42
landings whose framed post had its heart under the screen, the only heart on screen was another
post's. The button path liked that post and filed the like under the author read for the framed one.

It now likes through the like of a list of posts (`LikeOrchestration.like_framed_post`), the same as a
profile's posts and a hashtag's. The screens are real home feeds of that phone, anonymized:
- `ig410_fr_feed_heart_of_post_above_at_top.xml`: the post above's button row at the top of the
  list, the framed post's header at 10 % of the screen, its photo, its button row above the tabs;
- `ig410_fr_feed_caption_with_hashtags.xml`: the post above's photo, button row and long caption fill
  the screen, the framed post's header sits alone above the tabs.
`profile_posts_phone.py` replays them; a tap on a heart, or a double tap on a post, likes that post as
Instagram does.
"""

import pytest
from loguru import logger

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll as feed_scroll
import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as post_reading
import taktik.core.social_media.instagram.actions.business.actions.like.orchestration as orchestration
import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
from profile_posts_phone import HEADER_ID, HEART_ID, ProfilePostsPhone, bounds_of, capture, like_on_phone
from taktik.core.social_media.instagram.actions.business.workflows.feed.workflow import FeedBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SELECTORS

HEART_ABOVE = capture("ig410_fr_feed_heart_of_post_above_at_top.xml")
HEADER_ALONE_ABOVE_TABS = capture("ig410_fr_feed_caption_with_hashtags.xml")
PIXEL_3A_H = 2220


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, post_reading, feed_scroll, orchestration):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _feed(phone):
    """The Feed with the production like of a list (`LikeOrchestration`) on the replayed phone."""
    like = like_on_phone(phone)
    feed = object.__new__(FeedBusiness)
    feed.logger = logger.bind(module="test_feed_like_lands_on_the_framed_post")
    feed.like_business = like
    # What the Feed's own like read before it went through `like_framed_post` (red check).
    feed.device = like.device
    feed._feed_sel = FEED_SELECTORS
    feed._human_like_delay = lambda *_args, **_kwargs: None
    return feed


def _double_tap_drawn(monkeypatch, drawn: bool):
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: drawn)


def _hearts(xml):
    """(bounds, selected) of each heart, top to bottom, and the framed header's top."""
    from lxml import etree

    root = etree.fromstring(xml.encode("utf-8"))
    header_top = min(bounds_of(n)[1] for n in root.iter() if n.get("resource-id") == HEADER_ID)
    hearts = sorted(((bounds_of(n), n.get("selected")) for n in root.iter()
                     if n.get("resource-id") == HEART_ID), key=lambda item: item[0][1])
    return header_top, hearts


def test_the_button_path_taps_the_framed_posts_own_heart_not_the_post_above(monkeypatch):
    _double_tap_drawn(monkeypatch, False)
    phone = ProfilePostsPhone(screen=HEART_ABOVE, height=PIXEL_3A_H, likes_on_tap=True)
    header_top, hearts = _hearts(HEART_ABOVE)
    (above, _), (own, _) = hearts
    assert above[3] <= header_top < own[1], "the capture: a heart above the framed header, its own below"

    assert _feed(phone)._like_current_post() is True

    assert [kind for kind, _x, _y in phone.taps] == ["tap"]
    _kind, x, y = phone.taps[0]
    assert own[0] <= x <= own[2] and own[1] <= y <= own[3], f"tap at ({x}, {y}), the framed post's heart is {own}"
    after = _hearts(phone.dump_hierarchy())[1]
    assert [selected for bounds, selected in after] == ["false", "true"], "the post above was liked"


def test_the_double_tap_lands_on_the_framed_posts_own_media(monkeypatch):
    _double_tap_drawn(monkeypatch, True)
    phone = ProfilePostsPhone(screen=HEART_ABOVE, height=PIXEL_3A_H, likes_on_tap=True)
    header_top, hearts = _hearts(HEART_ABOVE)
    own = hearts[1][0]

    assert _feed(phone)._like_current_post() is True

    assert [kind for kind, _x, _y in phone.taps] == ["double_tap"]
    _kind, _x, y = phone.taps[0]
    assert header_top < y < own[1], f"double tap at y={y}: the framed post's media runs from {header_top} to {own[1]}"
    assert [selected for bounds, selected in _hearts(phone.dump_hierarchy())[1]] == ["false", "true"]


@pytest.mark.parametrize("double_tap", [True, False], ids=["double_tap", "heart"])
def test_no_feed_like_on_a_post_mostly_under_the_screen(monkeypatch, double_tap):
    # The post above fills the screen; the framed post shows its header alone above the tabs. Its
    # heart is a screen and a half away: a like would bring up a post not yet seen.
    _double_tap_drawn(monkeypatch, double_tap)
    phone = ProfilePostsPhone(screen=HEADER_ALONE_ABOVE_TABS, height=PIXEL_3A_H, likes_on_tap=True)
    feed = _feed(phone)

    assert feed._like_current_post() is False

    assert phone.taps == [], "a like went to the post above the framed one"
    assert feed.like_business.scroll_actions.gestures == [], "the like brought up a post mostly under the screen"
    assert feed.like_business.scroll_actions._last_buttons_reveal["reason"] == "post_mostly_under_screen"


def test_an_already_liked_framed_post_is_no_feed_like(monkeypatch):
    _double_tap_drawn(monkeypatch, True)
    phone = ProfilePostsPhone(screen=HEART_ABOVE, height=PIXEL_3A_H, likes_on_tap=True)
    own = _hearts(HEART_ABOVE)[1][1][0]
    phone._liked_hearts.add(f"[{own[0]},{own[1]}][{own[2]},{own[3]}]")

    assert _feed(phone)._like_current_post() is False

    assert phone.taps == []


def test_the_post_above_liked_does_not_make_the_framed_post_liked(monkeypatch):
    # The Feed read "already liked" on the first heart of the screen: the post above's.
    _double_tap_drawn(monkeypatch, False)
    phone = ProfilePostsPhone(screen=HEART_ABOVE, height=PIXEL_3A_H, likes_on_tap=True)
    above = _hearts(HEART_ABOVE)[1][0][0]
    phone._liked_hearts.add(f"[{above[0]},{above[1]}][{above[2]},{above[3]}]")

    assert _feed(phone)._like_current_post() is True

    assert [selected for bounds, selected in _hearts(phone.dump_hierarchy())[1]] == ["true", "true"]
