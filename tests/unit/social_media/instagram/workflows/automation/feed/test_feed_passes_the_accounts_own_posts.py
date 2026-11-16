"""A post of the account the run acts as is passed: no like, no comment, no visit.

Found by reading the code: the Feed liked a post of the operated account under its own name, and
opened its own profile when "visit the author" was on. The likers and followers loops already
passed that account (`ActionUtils.same_username` against `automation.active_username`); the Feed
now makes the same comparison, before the like and before the visit, and counts the post with the
other posts a filter left out (`posts_skipped_filter`).
"""

import types

import pytest

import taktik.core.social_media.instagram.workflows.automation.feed.workflow as feed_module
from taktik.core.shared.diagnostics import run_halt
from unit.social_media.instagram.workflows.automation.feed.test_feed_counts_posts_and_profiles import (
    _RUN,
    _feed,
)


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    run_halt.reinitialiser()
    monkeypatch.setattr(feed_module.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(feed_module.IPCEmitter, "emit_feed_decision", lambda *a, **k: None)
    yield
    run_halt.reinitialiser()


def _feed_as(account, authors):
    feed = _feed(authors=authors)
    feed.automation = types.SimpleNamespace(active_username=account)
    feed.liked = []
    feed.visited = []

    def _like(record_as=None):
        feed.liked.append(record_as)
        return True

    def _visit(username):
        feed.visited.append(username)
        return True

    feed._like_current_post = _like
    feed.nav_actions.navigate_to_profile = _visit
    return feed


def test_the_accounts_own_post_is_not_liked():
    feed = _feed_as("demo_account", ["ana", "Demo_Account", "cleo"])

    stats = feed.interact_with_feed(dict(_RUN))

    assert feed.liked == ["ana", "cleo"]
    assert stats["posts_skipped_filter"] == 1


def test_the_accounts_own_profile_is_not_visited():
    feed = _feed_as("@demo_account", ["demo_account", "bob", "demo_account"])

    feed.interact_with_feed({**_RUN, "interact_with_post_author": True})

    assert feed.visited == ["bob"]
    assert feed.liked == ["bob"]


def test_a_run_that_does_not_know_its_account_engages_every_post():
    feed = _feed_as(None, ["ana", "bob", "cleo"])

    feed.interact_with_feed(dict(_RUN))

    assert feed.liked == ["ana", "bob", "cleo"]
