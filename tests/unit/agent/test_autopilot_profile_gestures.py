"""The Taktik Agent autopilot's gestures on a visited profile, and the comment that follows a like.

Three defects found on review (2026-09-24):
- the extra likes on a profile called a `like_next_profile_post` that never existed, imported
  from a module that does not export `LikeBusiness`; the exception was swallowed and no extra
  like was ever given. They now go through `LikeBusiness.like_profile_posts`, the target
  workflows' sequence, on a business object carrying the account;
- a follow was counted on the card and nowhere else: no ledger row, so it escaped the daily cap
  and the unfollow never knew the bot had followed the profile;
- once the like cap was reached, the autopilot went on commenting posts it no longer liked. As
  in the Feed, a comment now follows a like that has just landed.
"""

import time

import pytest

import taktik.core.agent.scenarios.instagram_feed_autopilot as autopilot
import taktik.core.social_media.instagram.actions.atomic.interaction as interaction_module
import taktik.core.social_media.instagram.actions.business.actions.like as like_package
from taktik.core.agent.scenarios.instagram_feed_autopilot import TaktikAgentWorkflow
from taktik.core.shared.diagnostics import run_halt


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(autopilot.time, "sleep", lambda *_a, **_k: None)
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


class _Ledger:
    """The business object the rows are filed through."""

    def __init__(self):
        self.rows = []

    def _record_action(self, username, action_type, count=1, **_kwargs):
        self.rows.append((username, action_type, count))
        return True


class _Feed(_Ledger):
    def __init__(self, liked=True):
        super().__init__()
        self.liked = liked
        self.comments = []

    def _like_current_post(self, record_as=None):
        return self.liked

    def _comment_feed_post(self, author, config, comment_text=None):
        self.comments.append((author, comment_text))
        return {"commented": True}


def _agent(**quotas):
    agent = object.__new__(TaktikAgentWorkflow)
    agent._stop_requested = False
    agent._account_id = 42
    agent.device = None
    agent.device_manager = object()
    agent.ipc = None
    agent.stats = {"posts_seen": 0, "likes": 0, "follows": 0, "comments": 0}
    agent.quotas = {"max_posts_seen": 100, "max_likes": 80, "max_follows": 20, "max_comments": 10,
                    **quotas}
    agent._block_seen = lambda _action: False
    return agent


class _ProfileButton:
    def __init__(self, device):
        pass

    def get_follow_button_state(self):
        return "follow"

    def follow_user(self, username):
        return True


def test_a_follow_is_filed_in_the_ledger(monkeypatch):
    monkeypatch.setattr(interaction_module, "ClickActions", _ProfileButton)
    agent = _agent()
    ledger = _Ledger()
    agent._feed_business = lambda: ledger

    agent._do_follow("alice")

    assert agent.stats["follows"] == 1
    assert ledger.rows == [("alice", "FOLLOW", 1)]


class _LikeBusiness:
    built = []

    def __init__(self, device_manager, session_manager=None, automation=None):
        _LikeBusiness.built.append(automation)
        self.calls = []
        _LikeBusiness.last = self

    def like_profile_posts(self, username, max_likes=3, navigate_to_profile=True, **_kwargs):
        self.calls.append((username, max_likes, navigate_to_profile))
        return {"posts_liked": max_likes}


def test_the_extra_likes_go_through_the_production_profile_sequence(monkeypatch):
    _LikeBusiness.built = []
    monkeypatch.setattr(like_package, "LikeBusiness", _LikeBusiness)
    agent = _agent()

    agent._like_profile_posts("alice", 2)

    # The profile is already on screen: no second navigation. The likes are filed under the account.
    assert _LikeBusiness.last.calls == [("alice", 2, False)]
    assert _LikeBusiness.built[0].active_account_id == 42
    assert agent.stats["likes"] == 2


def test_the_extra_likes_never_pass_the_like_cap(monkeypatch):
    monkeypatch.setattr(like_package, "LikeBusiness", _LikeBusiness)
    agent = _agent(max_likes=5)
    agent.stats["likes"] = 4

    agent._like_profile_posts("alice", 2)

    assert _LikeBusiness.last.calls == [("alice", 1, False)]
    assert agent.stats["likes"] == 5


def test_no_extra_like_at_all_once_the_cap_is_reached(monkeypatch):
    _LikeBusiness.built = []
    monkeypatch.setattr(like_package, "LikeBusiness", _LikeBusiness)
    agent = _agent(max_likes=5)
    agent.stats["likes"] = 5

    agent._like_profile_posts("alice", 2)

    assert _LikeBusiness.built == []


_COMMENT = {"action": "like_comment", "comment": "Superbe lumiere"}


def test_a_comment_follows_a_like_that_landed():
    agent = _agent()
    feed = _Feed(liked=True)

    engaged, blocked = agent._engage_post(feed, "bob", "like_comment", _COMMENT)

    assert (engaged, blocked) == (True, False)
    assert feed.comments == [("bob", "Superbe lumiere")]


def test_no_comment_once_the_like_cap_is_reached():
    agent = _agent(max_likes=3)
    agent.stats["likes"] = 3
    feed = _Feed(liked=True)

    engaged, _blocked = agent._engage_post(feed, "bob", "like_comment", _COMMENT)

    assert engaged is False
    assert feed.comments == []


def test_no_comment_when_the_like_did_not_land():
    agent = _agent()
    feed = _Feed(liked=False)

    agent._engage_post(feed, "bob", "like_comment", _COMMENT)

    assert feed.comments == []


def test_the_run_stops_when_likes_and_follows_are_spent_even_with_comments_left():
    agent = _agent(max_likes=3, max_follows=1, max_comments=10)
    agent.stats.update(likes=3, follows=1, comments=0)

    assert agent._should_stop(time.time() + 600) is True
