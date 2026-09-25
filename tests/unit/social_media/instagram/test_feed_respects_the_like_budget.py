"""The Feed stops liking once the session's like budget is spent.

The session no longer ends on a per-type ceiling: a spent budget disables its own action through
`exhausted_intents()`, which the interaction engine reads. The Feed's direct like mode never read
it. The session re-runs the feed step until its duration, each pass liked up to its own
`max_interactions`, and a bench run with a like budget of 1 liked 6 and 8 posts in ten minutes.
"""

import types

import pytest

import taktik.core.social_media.instagram.actions.business.workflows.feed.workflow as feed_module
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import FEED_DEFAULTS
from taktik.core.social_media.instagram.actions.business.workflows.feed.workflow import FeedBusiness


def _log():
    return types.SimpleNamespace(
        debug=lambda *a, **k: None, info=lambda *a, **k: None, success=lambda *a, **k: None,
        warning=lambda *a, **k: None, error=lambda *a, **k: None,
    )


class _Stats:
    def increment(self, *_a, **_k):
        pass


class _Session:
    """The two calls the feed makes on the session: its interaction phase, its spent intents."""

    def __init__(self, like_budget, broken=False):
        self.like_budget = like_budget
        self.broken = broken
        self.likes = 0

    def start_interaction_phase(self):
        pass

    def exhausted_intents(self):
        if self.broken:
            raise RuntimeError("daily usage unreadable")
        return {"like"} if self.likes >= self.like_budget else set()


def _feed(session):
    feed = object.__new__(FeedBusiness)
    feed.logger = _log()
    feed.default_config = {**FEED_DEFAULTS}
    feed.session_manager = session
    feed.automation = None
    feed.stats_manager = _Stats()
    feed.nav_actions = types.SimpleNamespace(navigate_to_home=lambda: True)
    feed.scroll_actions = types.SimpleNamespace(
        human_reading_pause=lambda **k: None,
        scroll_feed_to_next_post=lambda **k: {"on_feed": True},
    )
    feed._is_sponsored_post = lambda: False
    feed._is_reel_post = lambda: False
    feed._get_current_post_author = lambda: "bob"
    feed.has_feed_suggestions_carousel = lambda: False
    feed._stop_if_action_blocked = lambda username, action: False
    feed.likes_sent = 0

    def _like(record_as=None):
        feed.likes_sent += 1
        session.likes += 1
        return True

    feed._like_current_post = _like
    return feed


_RUN = {
    "max_interactions": 3,
    "max_posts_to_check": 4,
    "like_percentage": 100,
    "comment_percentage": 0,
    "view_feed_stories": False,
    "follow_suggestions": False,
    "min_post_likes": 0,
    "max_post_likes": 0,
    "capture_ads": False,
    "interact_with_post_author": False,
    "interact_with_post_likers": False,
}


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    run_halt.reinitialiser()
    monkeypatch.setattr(feed_module.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(feed_module.IPCEmitter, "emit_feed_decision", lambda *a, **k: None)
    yield
    run_halt.reinitialiser()


def test_no_like_once_the_session_like_budget_is_spent():
    session = _Session(like_budget=1)
    feed = _feed(session)

    stats = feed.interact_with_feed(dict(_RUN))

    assert feed.likes_sent == 1
    assert stats["posts_liked"] == 1
    # The pass goes on as a view: the posts are still read, just not liked.
    assert stats["posts_checked"] == 4


def test_a_spent_budget_from_an_earlier_pass_blocks_the_first_like():
    session = _Session(like_budget=2)
    session.likes = 2
    feed = _feed(session)

    stats = feed.interact_with_feed(dict(_RUN))

    assert feed.likes_sent == 0
    assert stats["posts_liked"] == 0


def test_an_unreadable_budget_fails_open_like_the_rest_of_the_guard():
    session = _Session(like_budget=1, broken=True)
    feed = _feed(session)

    stats = feed.interact_with_feed(dict(_RUN))

    assert stats["posts_liked"] == 3
