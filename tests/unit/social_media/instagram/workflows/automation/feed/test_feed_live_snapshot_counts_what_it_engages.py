"""The live snapshot of a Feed run carries what the run engages: its posts, and the authors it visits.

The desktop reads a run's counters from the stats snapshot the bot sends after every increment
(`BaseStatsManager.get_summary`, sent as an `instagram_stats` line), and from the first snapshot on
it trusts nothing else. Two counts of the Feed never reached it:

- `posts_engaged`, the Feed's own output (its quota counts the posts it likes): the workflow moved
  it, but `get_summary` did not carry it, so every snapshot said 0 posts engaged and the hub card of
  a Feed run, measured against its quota, never moved;
- an author the run visits and engages (`interact_with_post_author`): counted in the run's final
  dict, never in the stats manager, so the live "interacted" count stayed at 0 while the likers walk,
  the same kind of visit, moved it.

And since 2026-10-18 (product decision) the author of a post the Feed liked is an account interacted
with, live as in the final dict, once however many of their posts the run engages or visits.
"""

import types

import pytest

import taktik.core.social_media.instagram.workflows.automation.feed.workflow as feed_module
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.base.stats import BaseStatsManager
from taktik.core.social_media.instagram.workflows.automation.feed.workflow import FeedBusiness
from taktik.core.social_media.instagram.workflows.automation.workflow_defaults import FEED_DEFAULTS


def _quiet():
    return types.SimpleNamespace(**{level: (lambda *a, **k: None) for level in ("debug", "info", "success", "warning", "error")})


def _feed(snapshots, author_interacts=True, one_author=False):
    """A Feed on a played phone: every post by another author (or all by one), every like landing."""
    screen = {"post": 1}

    def next_post(**_kwargs):
        screen["post"] += 1
        return {"on_feed": True}

    feed = object.__new__(FeedBusiness)
    feed.logger = _quiet()
    feed.default_config = {**FEED_DEFAULTS}
    feed.session_manager = None
    feed.automation = None
    feed.stats_manager = BaseStatsManager("feed")
    feed.stats_manager.set_on_stats_callback(snapshots.append)
    feed.nav_actions = types.SimpleNamespace(navigate_to_home=lambda: True, navigate_to_profile=lambda username: True)
    feed.profile_business = types.SimpleNamespace(get_complete_profile_info=lambda username, navigate_if_needed=False: {"username": username})
    feed.scroll_actions = types.SimpleNamespace(human_reading_pause=lambda **k: None, scroll_feed_to_next_post=next_post)
    feed._is_sponsored_post = lambda: False
    feed._is_reel_post = lambda: False
    feed._get_current_post_author = lambda: "author_1" if one_author else f"author_{screen['post']}"
    feed.has_feed_suggestions_carousel = lambda: False
    feed._stop_if_action_blocked = lambda username, action: False
    feed._like_current_post = lambda record_as=None: True
    feed._perform_interactions_on_profile = lambda username, config, profile_data=None: {
        "actually_interacted": author_interacts, "likes": 1 if author_interacts else 0,
    }
    return feed


_RUN = {
    "max_interactions": 2,
    "max_posts_to_check": 2,
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
def _quiet_run(monkeypatch):
    run_halt.reinitialiser()
    monkeypatch.setattr(feed_module.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(feed_module.IPCEmitter, "emit_feed_decision", lambda *a, **k: None)
    yield
    run_halt.reinitialiser()


def test_the_snapshot_carries_the_posts_the_feed_engaged():
    snapshots = []

    _feed(snapshots).interact_with_feed(dict(_RUN))

    assert snapshots, "the run must send its snapshots"
    assert snapshots[-1]["posts_engaged"] == 2
    assert snapshots[-1]["likes"] == 2
    # The two authors liked are two accounts interacted with; liking a post opens no profile.
    assert snapshots[-1]["profiles_interacted"] == 2
    assert snapshots[-1]["profiles_visited"] == 0


def test_an_author_liked_twice_is_one_account_live():
    snapshots = []

    _feed(snapshots, one_author=True).interact_with_feed(dict(_RUN))

    assert snapshots[-1]["posts_engaged"] == 2
    assert snapshots[-1]["profiles_interacted"] == 1


def test_an_author_visited_and_engaged_is_counted_live():
    snapshots = []

    _feed(snapshots).interact_with_feed({**_RUN, "interact_with_post_author": True})

    # Liked, then visited and engaged: each author is one account, visited once.
    assert snapshots[-1]["profiles_visited"] == 2
    assert snapshots[-1]["profiles_interacted"] == 2


def test_an_author_visit_that_did_nothing_is_not_an_interaction():
    snapshots = []

    feed = _feed(snapshots, author_interacts=False)
    feed.interact_with_feed({**_RUN, "like_percentage": 0, "interact_with_post_author": True})

    # Nothing liked, nothing done on the visits: no count moved, the summary says it.
    assert feed.stats_manager.get_summary()["profiles_interacted"] == 0
