"""The Feed files its likes and comments at the gesture, the way the hashtag posts pass does.

The hashtag posts pass was fixed on 2026-09-24: a like goes through `record_as` (ledger row and
session counter at the tap), a comment through `CommentAction.comment_on_post` (filed right after
the send), and a post whose author cannot be read is not engaged. The Feed liked and commented
the posts of the home feed with no ledger row and no session counter at all: its sessions were
aggregated to zero likes, its likes escaped the session and daily caps, and its comment
published text that nothing recorded, then closed the sheet with a back key uiautomator2
ignores.

Since the Feed likes through the like of a list of posts (`LikeOrchestration.like_framed_post`), a
like is filed once the framed post's heart is seen turned, never for a gesture that did not turn it.
The screen is a real home feed (Pixel 3a, Instagram 410 in French), anonymized, replayed by
`profile_posts_phone.py`.
"""

import inspect
import types

import pytest
from lxml import etree

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll as feed_scroll
import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as post_reading
import taktik.core.social_media.instagram.actions.business.actions.like.orchestration as orchestration
import taktik.core.social_media.instagram.actions.business.workflows.feed.workflow as feed_module
import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
from profile_posts_phone import HEART_ID, ProfilePostsPhone, bounds_of, capture, like_on_phone
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
    LikeOrchestration,
)
from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import FEED_DEFAULTS
from taktik.core.social_media.instagram.actions.business.workflows.feed.post_actions import (
    FeedPostActionsMixin,
)
from taktik.core.social_media.instagram.actions.business.workflows.feed.workflow import FeedBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

FEED_POST = capture("ig410_fr_feed_heart_of_post_above_at_top.xml")
PIXEL_3A_H = 2220


def _log():
    return types.SimpleNamespace(
        debug=lambda *a, **k: None, info=lambda *a, **k: None, success=lambda *a, **k: None,
        warning=lambda *a, **k: None, error=lambda *a, **k: None,
    )


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, post_reading, feed_scroll, orchestration):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


# ─────────────────────────────────────────────────────────────── the like gesture

def _feed_on_phone(phone):
    """The Feed whose like is the production like of a list, on the replayed phone."""
    feed = object.__new__(FeedBusiness)
    feed.logger = _log()
    feed.like_business = like_on_phone(phone)
    return feed


def _hearts(xml):
    """(bounds, selected) of each heart of the screen, top to bottom: the framed post's is the last."""
    root = etree.fromstring(xml.encode("utf-8"))
    return sorted(((bounds_of(n), n.get("selected")) for n in root.iter()
                   if n.get("resource-id") == HEART_ID), key=lambda item: item[0][1])


def _framed_heart_liked(phone) -> bool:
    return _hearts(phone.dump_hierarchy())[-1][1] == "true"


@pytest.mark.parametrize("double_tap", [False, True])
def test_a_feed_like_given_its_author_is_filed_once_its_heart_turns(monkeypatch, double_tap):
    """Button or double tap: one ledger row and one session count, under the author."""
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: double_tap)
    phone = ProfilePostsPhone(screen=FEED_POST, height=PIXEL_3A_H, likes_on_tap=True)
    feed = _feed_on_phone(phone)

    assert feed._like_current_post(record_as="bob") is True

    assert _framed_heart_liked(phone)
    assert feed.like_business.rows == [("bob", "LIKE", 1)]
    assert feed.like_business.session_actions == [("like_posts", "bob")]


@pytest.mark.parametrize("double_tap", [False, True])
def test_a_feed_gesture_whose_heart_does_not_turn_files_nothing(monkeypatch, double_tap):
    """The heart is what says the like took: a gesture Instagram did not take is no like, no row."""
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: double_tap)
    phone = ProfilePostsPhone(screen=FEED_POST, height=PIXEL_3A_H, likes_on_tap=False)
    feed = _feed_on_phone(phone)

    assert feed._like_current_post(record_as="bob") is False

    assert phone.taps, "no gesture was made"
    assert feed.like_business.rows == [] and feed.like_business.session_actions == []


def test_an_already_liked_feed_post_is_no_gesture_and_no_row():
    phone = ProfilePostsPhone(screen=FEED_POST, height=PIXEL_3A_H, likes_on_tap=True)
    own = _hearts(FEED_POST)[-1][0]
    phone._liked_hearts.add(f"[{own[0]},{own[1]}][{own[2]},{own[3]}]")
    feed = _feed_on_phone(phone)

    assert feed._like_current_post(record_as="bob") is False

    assert phone.taps == []
    assert feed.like_business.rows == [] and feed.like_business.session_actions == []


def test_the_feed_records_through_the_function_the_hashtag_pass_uses():
    """One way of liking a post of a list and filing it: the Feed has neither gesture nor ledger
    of its own."""
    assert "like_framed_post" in inspect.getsource(FeedPostActionsMixin._like_current_post)
    assert "record_post_like" in inspect.getsource(LikeOrchestration._like_framed_post)
    assert "_like_framed_post" in inspect.getsource(LikeOrchestration.like_current_post)


# ─────────────────────────────────────────────────────────────── the feed loop

class _Stats:
    def __init__(self):
        self.counts = {}

    def increment(self, name, value=1):
        self.counts[name] = self.counts.get(name, 0) + value


def _feed(author="bob", like_ok=True):
    feed = object.__new__(FeedBusiness)
    feed.logger = _log()
    feed.default_config = {**FEED_DEFAULTS}
    feed.session_manager = None
    feed.automation = None
    feed.stats_manager = _Stats()
    feed.nav_actions = types.SimpleNamespace(navigate_to_home=lambda: True)
    feed.scroll_actions = types.SimpleNamespace(
        human_reading_pause=lambda **k: None,
        scroll_feed_to_next_post=lambda **k: {"on_feed": True},
    )
    feed._is_sponsored_post = lambda: False
    feed._is_reel_post = lambda: False
    feed._get_current_post_author = lambda: author
    feed.has_feed_suggestions_carousel = lambda: False
    feed._stop_if_action_blocked = lambda username, action: False
    feed.likes = []
    feed.comments = []
    feed._like_current_post = lambda record_as=None: feed.likes.append(record_as) or like_ok
    feed.comment_business = types.SimpleNamespace(
        comment_on_post=lambda **kw: feed.comments.append(kw) or {"commented": True})
    return feed


_RUN = {
    "max_interactions": 2,
    "max_posts_to_check": 2,
    "like_percentage": 100,
    "comment_percentage": 100,
    "custom_comments": ["Superbe cadrage"],
    "view_feed_stories": False,
    "follow_suggestions": False,
    "min_post_likes": 0,
    "max_post_likes": 0,
    "capture_ads": False,
    "interact_with_post_author": False,
    "interact_with_post_likers": False,
}


@pytest.fixture
def cards(monkeypatch):
    run_halt.reinitialiser()
    cards = []
    monkeypatch.setattr(feed_module.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(feed_module.IPCEmitter, "emit_feed_decision",
                        lambda author, action, reason=None: cards.append((author, action, reason)))
    yield cards
    run_halt.reinitialiser()


def test_the_feed_likes_under_the_post_author(cards):
    feed = _feed()

    stats = feed.interact_with_feed(dict(_RUN))

    assert feed.likes == ["bob", "bob"]
    assert stats["likes_made"] == 2


def test_the_feed_comments_through_the_production_comment(cards):
    """`comment_on_post` files the comment at the send and closes the sheet it opened."""
    feed = _feed()

    stats = feed.interact_with_feed(dict(_RUN))

    assert [c["username"] for c in feed.comments] == ["bob", "bob"]
    assert feed.comments[0]["custom_comments"] == ["Superbe cadrage"]
    assert stats["comments_made"] == 2
    assert feed.stats_manager.counts["posts_engaged"] == 2


def test_a_comment_the_action_did_not_publish_is_not_counted(cards):
    feed = _feed()
    feed.comment_business = types.SimpleNamespace(comment_on_post=lambda **kw: {"commented": False})

    stats = feed.interact_with_feed(dict(_RUN))

    assert stats["comments_made"] == 0
    assert [c[1] for c in cards] == ["like", "like"]


def test_a_post_whose_author_cannot_be_read_is_not_engaged(cards):
    """No author: no ledger row, no deduplication, no cap. Neither like nor comment."""
    feed = _feed(author=None)

    stats = feed.interact_with_feed(dict(_RUN))

    assert feed.likes == [] and feed.comments == []
    assert stats["likes_made"] == 0 and stats.get("posts_engaged", 0) == 0
    assert cards == [(None, "skip", "Auteur illisible")] * 2


def test_the_whole_chain_leaves_one_row_per_like(cards, monkeypatch):
    """The loop with the real like on the real screen: the session sees the like of the run."""
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: False)
    feed = _feed()
    del feed._like_current_post
    phone = ProfilePostsPhone(screen=FEED_POST, height=PIXEL_3A_H, likes_on_tap=True)
    feed.like_business = like_on_phone(phone)

    feed.interact_with_feed({**_RUN, "comment_percentage": 0, "max_interactions": 1, "max_posts_to_check": 1})

    assert feed.like_business.rows == [("bob", "LIKE", 1)]
    assert feed.like_business.session_actions == [("like_posts", "bob")]
