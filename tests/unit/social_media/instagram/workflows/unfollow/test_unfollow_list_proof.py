"""A read of a follow list proves its end against the tab's exact count (review of 2026-09-24)."""

import pytest

from fake_follow_list import FakeFacade, FakeScreen, follow_list_xml, unified_tabs
from taktik.core.social_media.instagram.actions.business.workflows.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.list_proof import (
    count_tolerance,
    parse_tab_count,
    read_is_complete,
    scrolls_for,
)
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.mixins import (
    sync_followers as followers_mixin,
    sync_following as following_mixin,
)
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale


# ── The count of a tab title ──────────────────────────────────────────────────

@pytest.mark.parametrize("title, labels, count", [
    ("1 287 suivi(e)s", ["suivi(e)s"], 1287),
    ("673 followers", ["followers", "abonnés"], 673),
    ("48 following", ["following", "Following"], 48),
    ("1,287 followers", ["followers"], 1287),
    ("2 333 suivi(e)s", ["suivi(e)s"], 2333),
    ("12,3 k followers", ["followers"], None),       # abbreviated: not exact
    ("1.2M followers", ["followers"], None),
    ("0 abonnements", ["followers", "abonnés"], None),  # another tab
    ("", ["followers"], None),
])
def test_the_exact_count_of_a_tab_title(title, labels, count):
    assert parse_tab_count(title, labels) == count


def test_a_read_is_complete_only_near_the_exact_count_and_without_a_failed_scroll():
    assert read_is_complete(673, 673, False)
    assert read_is_complete(673 - count_tolerance(673), 673, False)
    assert not read_is_complete(150, 673, False)
    assert not read_is_complete(673, 673, True)       # a scroll failed on the way
    assert not read_is_complete(673, None, False)     # no count to prove against


def test_the_scroll_bound_follows_the_count():
    assert scrolls_for(None, 100) == 100
    assert scrolls_for(200, 100) == 100
    assert scrolls_for(3000, 100) > 450


# ── The two syncs, on a scripted list ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def _french_and_fast(monkeypatch):
    set_active_locale("fr")
    monkeypatch.setattr(unfollow_workflow.time, "sleep", lambda _s: None)
    monkeypatch.setattr(UnfollowBusiness, "following_tab_timeout", 0.0)
    monkeypatch.setattr(UnfollowBusiness, "list_load_timeout", 0.0)
    yield
    set_active_locale(None)


class Graph:
    """The follow graph service, in memory."""

    def __init__(self, known_followings=()):
        self.known = {name.lower() for name in known_followings}
        self.followings, self.followers, self.unfollowed = [], [], []

    def install(self, monkeypatch):
        for module in (followers_mixin, following_mixin):
            service = module.InstagramFollowGraphService
            monkeypatch.setattr(service, "get_active_following_usernames", staticmethod(lambda _a: set(self.known)))
            monkeypatch.setattr(service, "has_bot_follow_record", staticmethod(lambda _u, _a: False))
            monkeypatch.setattr(service, "upsert_following",
                                staticmethod(lambda username, **_k: self.followings.append(username) or "new"))
            monkeypatch.setattr(service, "upsert_follower",
                                staticmethod(lambda username, **_k: self.followers.append(username) or "new"))
            monkeypatch.setattr(service, "mark_unfollowed",
                                staticmethod(lambda username, _a: self.unfollowed.append(username)))


def _business(screens, *, graph, monkeypatch):
    screen = FakeScreen(*screens)
    business = UnfollowBusiness(FakeFacade(screen))
    business._get_account_id = lambda: 1
    business.nav_actions.navigate_to_profile_tab = lambda: True
    business.nav_actions.open_followers_list = lambda: True
    business.nav_actions.open_following_list = lambda: True
    business._set_following_list_sort = lambda order: False
    business._scroll_followers_list = lambda: screen.advance() or True
    business._scroll_following_list = lambda: screen.advance() or True
    graph.install(monkeypatch)
    return business, screen


FOLLOWERS_TITLES = ("{n} followers", "4 suivi(e)s", "0 abonnements", "À vérifier")


def _followers_page(rows, count, selected=0):
    titles = tuple(title.format(n=count) for title in FOLLOWERS_TITLES)
    return follow_list_xml(rows, extra=unified_tabs(selected=selected, titles=titles))


def test_a_followers_read_that_reaches_the_count_is_complete(monkeypatch):
    graph = Graph()
    pages = [_followers_page([("f1", "Suivi(e)"), ("f2", "Suivre en retour")], 4),
             _followers_page([("f3", "Suivi(e)"), ("f4", "Suivre en retour")], 4)]
    business, _screen = _business(pages, graph=graph, monkeypatch=monkeypatch)

    stats = business.sync_followers_list({"mode": "fast"})

    assert stats["complete"] is True and stats["expected"] == 4
    assert stats["usernames"] == {"f1", "f2", "f3", "f4"}


def test_a_followers_read_that_stops_short_of_the_count_proves_nothing(monkeypatch):
    graph = Graph()
    pages = [_followers_page([("f1", "Suivi(e)"), ("f2", "Suivre en retour")], 400)]
    business, _screen = _business(pages, graph=graph, monkeypatch=monkeypatch)

    stats = business.sync_followers_list({"mode": "fast"})

    assert stats["end_reached"] is True and stats["complete"] is False


def test_suggestion_rows_under_the_followers_are_not_followers(monkeypatch):
    graph = Graph()
    pages = [_followers_page([("f1", "Suivi(e)"), ("f2", "Suivre en retour"),
                              ("suggested", "Suivre")], 2)]
    business, _screen = _business(pages, graph=graph, monkeypatch=monkeypatch)

    stats = business.sync_followers_list({"mode": "fast"})

    assert "suggested" not in stats["usernames"] and graph.followers == ["f1", "f2"]


def test_the_followers_sync_leaves_the_following_tab(monkeypatch):
    graph = Graph()
    rows = [("f1", "Suivi(e)")]
    pages = [_followers_page(rows, 1, selected=1), _followers_page(rows, 1, selected=0)]
    business, _screen = _business(pages, graph=graph, monkeypatch=monkeypatch)

    stats = business.sync_followers_list({"mode": "fast"})

    assert stats["complete"] is True and len(business.device.taps) == 1


FOLLOWING_TITLES = ("9 followers", "{n} suivi(e)s", "0 abonnements", "À vérifier")


def _following_page(rows, count):
    titles = tuple(title.format(n=count) for title in FOLLOWING_TITLES)
    return follow_list_xml(rows, extra=unified_tabs(selected=1, titles=titles))


def test_a_partial_following_read_marks_no_departure(monkeypatch):
    graph = Graph(known_followings=["a1", "a2", "gone"])
    pages = [_following_page([("a1", "Suivi(e)"), ("a2", "Suivi(e)")], 300)]
    business, _screen = _business(pages, graph=graph, monkeypatch=monkeypatch)

    stats = business.sync_following_list({"mode": "fast"})

    assert stats["complete"] is False and graph.unfollowed == []


def test_a_complete_following_read_marks_the_departures(monkeypatch):
    known = [f"a{i}" for i in range(1, 11)] + ["gone"]
    graph = Graph(known_followings=known)
    rows = [(f"a{i}", "Suivi(e)") for i in range(1, 11)]
    pages = [_following_page(rows[:5], 10), _following_page(rows[5:], 10)]
    business, _screen = _business(pages, graph=graph, monkeypatch=monkeypatch)

    stats = business.sync_following_list({"mode": "fast"})

    assert stats["complete"] is True and graph.unfollowed == ["gone"]


def test_too_many_departures_in_one_read_are_withheld(monkeypatch):
    graph = Graph(known_followings=["a1", "a2"] + [f"old{i}" for i in range(8)])
    pages = [_following_page([("a1", "Suivi(e)"), ("a2", "Suivi(e)")], 2)]
    business, _screen = _business(pages, graph=graph, monkeypatch=monkeypatch)

    stats = business.sync_following_list({"mode": "fast"})

    assert stats["complete"] is True
    assert graph.unfollowed == [] and stats["departures_withheld"] == 8


def test_suggestion_rows_under_the_following_list_are_not_followings(monkeypatch):
    graph = Graph()
    pages = [_following_page([("a1", "Suivi(e)"), ("suggested", "Suivre")], 1)]
    business, _screen = _business(pages, graph=graph, monkeypatch=monkeypatch)

    business.sync_following_list({"mode": "fast"})

    assert graph.followings == ["a1"]
