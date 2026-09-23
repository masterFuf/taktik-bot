"""U7: the follow graph follows what the bot really did.

A verified unfollow closes the following row, a bot follow (or a re-follow) reopens it, and a
complete read of the following list closes the rows of accounts unfollowed elsewhere.
"""

import logging

import pytest

from taktik.core.database import instagram_follow_graph
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.mixins import sync_following
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.mixins.sync_following import (
    SyncFollowingMixin,
)


class _GraphSpy:
    def __init__(self):
        self.calls = []

    def upsert_following(self, **kwargs):
        self.calls.append(("upsert_following", kwargs))
        return "new"

    def mark_unfollowed(self, username, account_id):
        self.calls.append(("mark_unfollowed", {"username": username, "account_id": account_id}))


@pytest.fixture
def graph(monkeypatch):
    spy = _GraphSpy()
    monkeypatch.setattr(instagram_follow_graph, "InstagramFollowGraphService", spy)
    monkeypatch.setattr(sync_following, "InstagramFollowGraphService", spy)
    return spy


def test_a_recorded_unfollow_closes_the_following_row(graph):
    InstagramWorkflowStateService._update_follow_graph("alice", "UNFOLLOW", 3)
    assert graph.calls == [("mark_unfollowed", {"username": "alice", "account_id": 3})]


def test_a_bot_follow_opens_the_following_row_as_the_bots(graph):
    InstagramWorkflowStateService._update_follow_graph("bob", "FOLLOW", 3)
    assert graph.calls == [("upsert_following", {
        "username": "bob", "display_name": "", "account_id": 3,
        "followed_by_bot": True, "source": "bot_follow"})]


def test_other_actions_leave_the_graph_alone(graph):
    for action in ("LIKE", "COMMENT", "STORY_WATCH"):
        InstagramWorkflowStateService._update_follow_graph("carol", action, 3)
    assert graph.calls == []


class _Sync(SyncFollowingMixin):
    logger = logging.getLogger("test-departures")


def test_a_complete_read_closes_the_accounts_unfollowed_elsewhere(graph):
    gone = _Sync()._record_following_departures(3, known={"alice", "bob", "carol"}, seen={"Alice", "carol"})
    assert gone == 1
    assert graph.calls == [("mark_unfollowed", {"username": "bob", "account_id": 3})]
