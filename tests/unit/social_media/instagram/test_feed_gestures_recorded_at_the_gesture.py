"""The Feed files its likes and comments at the gesture, the way the hashtag posts pass does.

The hashtag posts pass was fixed on 2026-09-24: a like goes through `record_as` (ledger row and
session counter at the tap), a comment through `CommentAction.comment_on_post` (filed right after
the send), and a post whose author cannot be read is not engaged. The Feed liked and commented
the posts of the home feed with no ledger row and no session counter at all: its sessions were
aggregated to zero likes, its likes escaped the session and daily caps, and its comment
published text that nothing recorded, then closed the sheet with a back key uiautomator2
ignores.
"""

import types

import pytest

import taktik.core.social_media.instagram.actions.business.workflows.feed.post_actions as pa
import taktik.core.social_media.instagram.actions.business.workflows.feed.workflow as feed_module
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
    LikeOrchestration,
)
from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import FEED_DEFAULTS
from taktik.core.social_media.instagram.actions.business.workflows.feed.post_actions import (
    FeedPostActionsMixin,
)
from taktik.core.social_media.instagram.actions.business.workflows.feed.workflow import FeedBusiness
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FeedSelectors


def _log():
    return types.SimpleNamespace(
        debug=lambda *a, **k: None, info=lambda *a, **k: None, success=lambda *a, **k: None,
        warning=lambda *a, **k: None, error=lambda *a, **k: None,
    )


class _Session:
    def __init__(self):
        self.actions = []

    def record_action(self, action_type, success=True, source=None):
        self.actions.append((action_type, source))


def _like_business():
    """The real recording function, with its two writes captured."""
    like = LikeOrchestration.__new__(LikeOrchestration)
    like.logger = _log()
    like.session_manager = _Session()
    like.rows = []
    like._record_action = lambda u, k, c=1, **kw: like.rows.append((u, k, c))
    return like


# ─────────────────────────────────────────────────────────────── the like gesture

class _El:
    def __init__(self, exists=False, content_desc=""):
        self.exists = exists
        self.attrib = {"content-desc": content_desc}


class _FeedSel:
    like_button = ["like_sel"]
    already_liked_indicators = ["already_sel"]
    liked_button_desc_fragments = FeedSelectors().liked_button_desc_fragments


class _Device:
    def __init__(self, elements):
        self._elements = elements

    def xpath(self, selector):
        return self._elements.get(selector, _El(exists=False))

    @property
    def info(self):
        return {"displayWidth": 1080, "displayHeight": 1920}

    def human_double_tap(self, bounds, *, rng=None):
        return (1, 2)

    def double_click(self, x, y):
        pass


class _Probe(FeedPostActionsMixin):
    def __init__(self, elements):
        self.device = _Device(elements)
        self._feed_sel = _FeedSel()
        self.logger = _log()
        self.like_business = _like_business()

    def _human_tap_element(self, element):
        return True

    def _human_like_delay(self, kind):
        pass


@pytest.mark.parametrize("double_tap", [False, True])
def test_a_feed_like_given_its_author_is_filed_at_the_gesture(monkeypatch, double_tap):
    """Button or image double-tap: one ledger row and one session count, under the author."""
    monkeypatch.setattr(pa, "_should_double_tap_like", lambda rng=None: double_tap)
    probe = _Probe({"like_sel": _El(exists=True, content_desc="Like")})

    assert probe._like_current_post(record_as="bob") is True

    assert probe.like_business.rows == [("bob", "LIKE", 1)]
    assert probe.like_business.session_manager.actions == [("like_posts", "bob")]


def test_a_feed_like_is_filed_before_the_pause_that_follows_it(monkeypatch):
    """A run stopped during the pause after the tap keeps the row of the like it gave."""
    class _Stopped(BaseException):
        pass

    monkeypatch.setattr(pa, "_should_double_tap_like", lambda rng=None: False)
    probe = _Probe({"like_sel": _El(exists=True, content_desc="Like")})

    def _stopped(_kind):
        raise _Stopped()

    probe._human_like_delay = _stopped
    with pytest.raises(_Stopped):
        probe._like_current_post(record_as="bob")

    assert probe.like_business.rows == [("bob", "LIKE", 1)]


def test_an_already_liked_feed_post_is_no_gesture_and_no_row():
    probe = _Probe({"like_sel": _El(exists=True, content_desc="Unlike")})

    assert probe._like_current_post(record_as="bob") is False

    assert probe.like_business.rows == [] and probe.like_business.session_manager.actions == []


def test_the_feed_records_through_the_function_the_hashtag_pass_uses():
    """One way of filing a post like. The Feed keeps its own gesture, not its own ledger."""
    import inspect

    source = inspect.getsource(FeedPostActionsMixin._record_feed_like)
    assert "record_post_like" in source
    assert "record_post_like" in inspect.getsource(LikeOrchestration.like_current_post)


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
    """The loop with the real like recording: the session sees every like of the run."""
    monkeypatch.setattr(pa, "_should_double_tap_like", lambda rng=None: False)
    feed = _feed()
    del feed._like_current_post
    feed.device = _Device({"like_sel": _El(exists=True, content_desc="Like")})
    feed._feed_sel = _FeedSel()
    feed._human_tap_element = lambda element: True
    feed._human_like_delay = lambda kind: None
    feed.like_business = _like_business()

    feed.interact_with_feed({**_RUN, "comment_percentage": 0})

    assert feed.like_business.rows == [("bob", "LIKE", 1)] * 2
    assert feed.like_business.session_manager.actions == [("like_posts", "bob")] * 2
