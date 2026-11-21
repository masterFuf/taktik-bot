"""After a stop, the Feed makes no gesture: no way back to the feed, no suggestions pass, no next post.

Kevin's rule of 2026-11-16: once the run is asked to stop (a lost network, a block, the desktop gone),
the phone is left as the stop found it. The Feed's two excursions, the author's profile and the likers
of a post, went back home in their `finally` whatever happened, and the loop then looked for the
suggestions carousel and swiped to the next post before it read the latch again.

The phone is played by doubles that write down the gestures asked of it: no screen is read here.
"""

import types

import taktik.core.social_media.instagram.workflows.automation.feed.workflow as feed_module
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.base.stats import create_workflow_stats
from taktik.core.social_media.instagram.workflows.automation.feed.workflow import FeedBusiness
from taktik.core.social_media.instagram.workflows.automation.workflow_defaults import FEED_DEFAULTS

_QUIET = types.SimpleNamespace(**{level: (lambda *a, **k: None)
                                   for level in ("debug", "info", "success", "warning", "error")})


def _stop_now():
    run_halt.demander_arret(run_halt.NETWORK_LOST, "the network watch lost the phone")


def _feed(gestures, *, stop_on_the_author=False, stop_on_the_like=False):
    feed = object.__new__(FeedBusiness)
    feed.logger = _QUIET
    feed.default_config = {**FEED_DEFAULTS}
    feed.session_manager = None
    feed.automation = None
    feed.stats_manager = types.SimpleNamespace(increment=lambda *a, **k: None)
    feed.nav_actions = types.SimpleNamespace(
        navigate_to_home=lambda: gestures.append("home") or True,
        navigate_to_profile=lambda username: gestures.append(f"profile:{username}") or True,
    )
    feed.profile_business = types.SimpleNamespace(
        get_complete_profile_info=lambda *a, **k: {"username": "post_author"})
    feed.scroll_actions = types.SimpleNamespace(human_reading_pause=lambda **k: gestures.append("reading"))
    feed._advance_to_next_post = lambda *a, **k: gestures.append("next_post") or {"on_feed": True}
    feed._is_sponsored_post = lambda: False
    feed._is_reel_post = lambda: False
    feed._get_current_post_author = lambda: "post_author"
    feed._stop_if_action_blocked = lambda username, action: False

    def like(record_as=None):
        gestures.append("like")
        if stop_on_the_like:
            _stop_now()
        return True

    feed._like_current_post = like
    feed.has_feed_suggestions_carousel = lambda: True
    feed.run_feed_suggestions_pass = lambda config: gestures.append("suggestions_pass") or {"follows": 0}

    def interactions(username, config, profile_data=None):
        if stop_on_the_author:
            _stop_now()
        return {"actually_interacted": False}

    feed._perform_interactions_on_profile = interactions
    return feed


def test_a_stop_during_the_author_visit_leaves_the_profile_on_screen():
    gestures = []
    feed = _feed(gestures, stop_on_the_author=True)

    feed._engage_post_author("post_author", {}, create_workflow_stats("feed"))

    assert gestures == ["profile:post_author"]


def test_without_a_stop_the_author_visit_hands_the_feed_back():
    gestures = []
    feed = _feed(gestures)

    feed._engage_post_author("post_author", {}, create_workflow_stats("feed"))

    assert gestures == ["profile:post_author", "home"]


def _likers_feed(gestures, *, stop_in_the_walk):
    feed = _feed(gestures)
    feed._open_likers_popup = lambda is_reel: gestures.append("likers_sheet") or True

    def walk(stats, **_kw):
        if stop_in_the_walk:
            _stop_now()

    feed._interact_with_likers_list = walk
    return feed


def test_a_stop_during_the_likers_walk_leaves_the_sheet_on_screen():
    gestures = []
    feed = _likers_feed(gestures, stop_in_the_walk=True)

    feed._engage_post_likers({}, create_workflow_stats("feed"))

    assert gestures == ["likers_sheet"]


def test_without_a_stop_the_likers_walk_hands_the_feed_back():
    gestures = []
    feed = _likers_feed(gestures, stop_in_the_walk=False)

    feed._engage_post_likers({}, create_workflow_stats("feed"))

    assert gestures == ["likers_sheet", "home"]


def _one_post_run(feed, monkeypatch):
    monkeypatch.setattr(feed_module.time, "sleep", lambda *_a: None)
    return feed.interact_with_feed({
        "interact_with_post_author": True,
        "like_percentage": 100,
        "comment_percentage": 0,
        "max_interactions": 5,
        "max_posts_to_check": 1,
        "follow_suggestions": True,
        "max_suggestion_passes": 1,
    })


def test_a_stop_during_the_author_visit_ends_the_loop_without_a_gesture(monkeypatch):
    """No suggestions pass and no swipe after the stop: the loop reads the latch before either."""
    gestures = []
    feed = _feed(gestures, stop_on_the_author=True)

    _one_post_run(feed, monkeypatch)

    assert gestures == ["home", "like", "reading", "profile:post_author"]


def test_a_stop_during_the_like_reads_nothing_more_and_visits_nobody(monkeypatch):
    """The reading pause browses a carousel, the visit opens a profile: both are gestures."""
    gestures = []
    feed = _feed(gestures, stop_on_the_like=True)

    _one_post_run(feed, monkeypatch)

    assert gestures == ["home", "like"]


def test_without_a_stop_the_loop_goes_on_to_the_suggestions_and_the_next_post(monkeypatch):
    gestures = []
    feed = _feed(gestures)

    _one_post_run(feed, monkeypatch)

    assert gestures == ["home", "like", "reading", "profile:post_author", "home",
                        "suggestions_pass", "next_post"]
