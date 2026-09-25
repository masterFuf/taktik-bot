"""The Taktik Agent feed autopilot files its likes and comments, the way the Feed does.

It liked through `FeedBusiness._like_current_post()` without `record_as` and commented through
`_comment_current_post`, which recorded nothing: no ledger row, no session counter, its gestures
escaping the daily caps. And its FeedBusiness was built without an identity, so even a recorded
gesture would have been refused ("Cannot record LIKE - no account_id").

It now goes through the Feed's own recording, the one mechanism: the like with
`record_as=author` (`LikeBusiness.record_post_like`), the comment with `_comment_feed_post`
(`CommentAction.comment_on_post(username=author)`), on a FeedBusiness carrying the account id.
A post whose author cannot be read is not engaged.
"""

import time

import pytest

import taktik.core.agent.scenarios.instagram_feed_autopilot as autopilot
import taktik.core.social_media.instagram.actions.business.workflows.feed as feed_package
from taktik.core.agent.scenarios.instagram_feed_autopilot import TaktikAgentWorkflow
from taktik.core.shared.diagnostics import run_halt

_FEED_SCREEN = (
    '<hierarchy rotation="0"><node class="android.widget.FrameLayout" package="com.instagram.android">'
    '<node text="bob" resource-id="com.instagram.android:id/row_feed_photo_profile_name"/>'
    '</node></hierarchy>'
)


class _Phone:
    def dump_hierarchy(self, *a, **k):
        return _FEED_SCREEN


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(autopilot.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(autopilot.random, "randint", lambda *_a: 1)
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


class _Feed:
    """Records how it was built and every gesture asked of it."""

    built = []

    def __init__(self, device_manager, *args, **kwargs):
        _Feed.built.append(kwargs.get("automation"))
        self.author = "bob"
        self.likes = []
        self.comments = []

    def _scroll_to_next_post(self):
        pass

    def _is_sponsored_post(self):
        return False

    def _is_reel_post(self):
        return False

    def _get_current_post_author(self):
        return self.author

    def _like_current_post(self, record_as=None):
        self.likes.append(record_as)
        return True

    def _comment_feed_post(self, author, config, comment_text=None):
        self.comments.append((author, comment_text))
        return {"commented": True}


class _AI:
    def decide_feed_action(self, **_kwargs):
        return {"action": "like_comment", "comment": "Superbe lumiere", "visit_profile": False,
                "cost_usd": 0.0, "reason": "test"}


def _agent(author="bob"):
    agent = object.__new__(TaktikAgentWorkflow)
    agent._stop_requested = False
    agent._account_id = 42
    agent.device = _Phone()
    agent.device_manager = None
    agent.config = {"skip_reels": True}
    agent.ipc = None
    agent.stats = {"posts_seen": 0, "posts_stopped": 0, "likes": 0, "follows": 0, "comments": 0,
                   "profile_visits": 0, "profiles_skipped_relationship": 0, "session_cost_usd": 0.0}
    agent.quotas = {"max_posts_seen": 2, "max_likes": 80, "max_follows": 20, "max_comments": 10,
                    "max_profile_visits": 10, "session_duration_min": 5}
    agent._consecutive_skips = 0
    agent._hashtag_pool = []
    agent._ai = _AI()
    agent._take_screenshot = lambda _label: "/tmp/shot.png"
    agent._session_start = time.time()
    agent._persona_block = ""
    return agent


def _run(monkeypatch, author="bob"):
    _Feed.built = []
    feeds = []

    def _make(device_manager, *args, **kwargs):
        feed = _Feed(device_manager, *args, **kwargs)
        feed.author = author
        feeds.append(feed)
        return feed

    monkeypatch.setattr(feed_package, "FeedBusiness", _make)
    agent = _agent()
    agent._run_feed_loop()
    return agent, feeds[0]


def test_the_feed_it_engages_through_carries_the_account(monkeypatch):
    _run(monkeypatch)

    identity = _Feed.built[0]
    assert identity is not None and identity.active_account_id == 42


def test_a_like_is_filed_under_the_post_author(monkeypatch):
    agent, feed = _run(monkeypatch)

    assert feed.likes == ["bob", "bob"]
    assert agent.stats["likes"] == 2


def test_a_comment_goes_through_the_feed_comment_with_the_ai_text(monkeypatch):
    agent, feed = _run(monkeypatch)

    assert feed.comments == [("bob", "Superbe lumiere")] * 2
    assert agent.stats["comments"] == 2


def test_a_post_whose_author_cannot_be_read_is_not_engaged(monkeypatch):
    agent, feed = _run(monkeypatch, author=None)

    assert feed.likes == [] and feed.comments == []
    assert agent.stats["likes"] == 0 and agent.stats["comments"] == 0
