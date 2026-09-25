"""The Feed reports two counts, each its own: the posts it liked, the profiles it engaged.

At the end of the loop `users_interacted` was written over with the number of posts liked: a run
that visited three authors and liked two posts reported two profiles, and one that liked five
posts without visiting anybody reported five. And the likers walk ran on the run's own count,
while its budget is per post: once the author visits and the first post's likers had reached
`max_likers_per_post`, the next post's walk stopped before its first liker.
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


def _feed(author_engaged=True, likers_per_walk=0):
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
    feed._get_current_post_author = lambda: "bob"
    feed.has_feed_suggestions_carousel = lambda: False
    feed._stop_if_action_blocked = lambda username, action: False
    feed._like_current_post = lambda record_as=None: True
    feed._engage_post_author = lambda username, config, stats: author_engaged
    feed._open_likers_popup = lambda is_reel: True
    feed.walks = []

    def _walk(stats, effective_config, max_interactions, source_type, source_name, list_source=None):
        # The shared loop's contract: it walks while ITS count is under the budget.
        feed.walks.append(stats['users_interacted'])
        while stats['users_interacted'] < min(max_interactions, likers_per_walk):
            stats['users_interacted'] += 1
            stats['users_found'] += 1

    feed._interact_with_likers_list = _walk
    return feed


_RUN = {
    "max_interactions": 3,
    "max_posts_to_check": 3,
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


def test_a_run_that_visits_the_authors_reports_them_and_its_likes_apart():
    feed = _feed(author_engaged=True)

    stats = feed.interact_with_feed({**_RUN, "interact_with_post_author": True})

    assert stats["posts_liked"] == 3
    assert stats["users_interacted"] == 3


def test_a_run_that_only_likes_posts_engaged_no_profile():
    feed = _feed()

    stats = feed.interact_with_feed(dict(_RUN))

    assert stats["posts_liked"] == 3
    assert stats["users_interacted"] == 0


def test_an_author_visit_that_did_nothing_is_not_a_profile_engaged():
    feed = _feed(author_engaged=False)

    stats = feed.interact_with_feed({**_RUN, "interact_with_post_author": True})

    assert stats["users_interacted"] == 0
    assert stats["posts_liked"] == 3


def test_every_post_walks_its_own_likers_budget():
    feed = _feed(likers_per_walk=2)

    stats = feed.interact_with_feed({**_RUN, "interact_with_post_likers": True,
                                     "max_likers_per_post": 2})

    assert feed.walks == [0, 0, 0]
    assert stats["users_interacted"] == 6
    assert stats["users_found"] == 6
