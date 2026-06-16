"""Tests for the TikTok new-followers workflow methods (inbox v2 - Phase 1).

On injecte un faux `dm` (DMActions) et on bypass l'init lourd du workflow pour valider
l'orchestration : ouverture de page, dédup du scrape, émission des callbacks, et résultats
de follow-back. Aucune dépendance device réelle.
"""

import types

from taktik.core.social_media.tiktok.actions.business.workflows.dm.workflow import (
    DMConfig,
    DMWorkflow,
)


class FakeDM:
    def __init__(self, followers=None, can_open=True, follow_results=None):
        self._followers = followers or []
        self._can_open = can_open
        self._follow_results = follow_results or {}
        self.open_calls = 0
        self.scroll_calls = 0
        self.followed = []

    def open_new_followers_page(self):
        self.open_calls += 1
        return self._can_open

    def get_new_followers(self, max_items=50):
        # Renvoie toujours la même liste -> exerce la dédup côté workflow
        return list(self._followers)

    def scroll_inbox(self, direction):
        self.scroll_calls += 1

    def follow_back(self, username):
        self.followed.append(username)
        return self._follow_results.get(username, True)


def _make_workflow(fake_dm):
    """Construit un DMWorkflow sans son __init__ lourd, avec juste ce qu'il faut."""
    wf = DMWorkflow.__new__(DMWorkflow)
    wf.dm = fake_dm
    wf._running = True
    wf.config = DMConfig(delay_between_conversations=0)
    wf._on_new_follower_callback = None
    wf._on_follow_back_result_callback = None
    wf.logger = types.SimpleNamespace(
        info=lambda *a, **k: None,
        error=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        debug=lambda *a, **k: None,
    )
    wf._handle_popups = lambda **kw: None
    return wf


def test_read_new_followers_scrapes_and_dedups_and_emits():
    followers = [
        {"username": "alice", "activity": "a commencé à te suivre", "can_follow_back": True},
        {"username": "bob", "activity": "a commencé à te suivre", "can_follow_back": True},
        {"username": "carol", "activity": "a commencé à te suivre", "can_follow_back": False},
    ]
    fake = FakeDM(followers=followers)
    wf = _make_workflow(fake)

    emitted = []
    wf.set_on_new_follower_callback(lambda f: emitted.append(f["username"]))

    # max_items == len(followers) -> pas de scroll ni de sleep
    result = wf.read_new_followers(max_items=3)

    assert [f["username"] for f in result] == ["alice", "bob", "carol"]
    assert emitted == ["alice", "bob", "carol"]
    assert fake.open_calls == 1
    assert fake.scroll_calls == 0  # tout tient dans le 1er passage


def test_read_new_followers_returns_empty_when_page_unavailable():
    fake = FakeDM(followers=[{"username": "x"}], can_open=False)
    wf = _make_workflow(fake)
    assert wf.read_new_followers(max_items=10) == []


def test_follow_back_users_executes_and_reports_per_username():
    fake = FakeDM(follow_results={"alice": True, "bob": False})
    wf = _make_workflow(fake)

    results_cb = []
    wf.set_on_follow_back_result_callback(lambda r: results_cb.append(r))

    results = wf.follow_back_users(["alice", "bob"])

    assert fake.followed == ["alice", "bob"]
    assert results == [
        {"username": "alice", "success": True},
        {"username": "bob", "success": False},
    ]
    assert results_cb == results


def test_follow_back_users_marks_all_failed_when_page_unavailable():
    fake = FakeDM(can_open=False)
    wf = _make_workflow(fake)

    results = wf.follow_back_users(["alice", "bob"])
    assert all(r["success"] is False for r in results)
    assert {r["username"] for r in results} == {"alice", "bob"}
    assert fake.followed == []  # jamais tenté de suivre


def test_follow_back_users_empty_list_is_noop():
    fake = FakeDM()
    wf = _make_workflow(fake)
    assert wf.follow_back_users([]) == []
    assert fake.open_calls == 0
