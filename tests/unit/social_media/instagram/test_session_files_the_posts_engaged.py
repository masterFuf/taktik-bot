"""A session is filed with the posts it engaged.

`posts_engaged` exists because the feed engages POSTS and visits no profile: a session snapshot
aggregated from the per-profile ledger came out empty, and the session was hidden. The count was
then read at finalisation from `automation.actions.stats_manager`, an attribute the actions
facade does not have (it keeps its manager under `stats`), so every session was filed with zero
posts. And the feed runner built a new FeedBusiness for each step, whose manager held the count.
"""

import time
import types

import taktik.core.social_media.instagram.workflows.support.workflow_helpers as helpers_module
from taktik.core.social_media.instagram.workflows.core.workflow_runner import WorkflowRunner
from taktik.core.social_media.instagram.workflows.support.workflow_helpers import WorkflowHelpers


class _Db:
    def __init__(self):
        self.calls = []

    def finalize_session(self, session_id, status, **kwargs):
        self.calls.append((session_id, status, kwargs))
        return True


def _manager(posts):
    return types.SimpleNamespace(stats={'posts_engaged': posts})


def _automation(**owners):
    return types.SimpleNamespace(
        stats={'start_time': time.time()},
        # The actions facade as it is: a `stats` manager, no `stats_manager`.
        actions=types.SimpleNamespace(stats=_manager(0)),
        **owners,
    )


def _finalize(monkeypatch, automation):
    db = _Db()
    monkeypatch.setattr(helpers_module, "get_local_database", lambda: db)
    assert WorkflowHelpers(automation).update_workflow_session(1590, 'COMPLETED') is True
    return db.calls[0][2]['posts_engaged']


def test_a_feed_session_is_filed_with_its_engaged_posts(monkeypatch):
    automation = _automation(feed_business=types.SimpleNamespace(stats_manager=_manager(3)))

    assert _finalize(monkeypatch, automation) == 3


def test_a_posts_only_hashtag_session_is_filed_with_its_engaged_posts(monkeypatch):
    automation = _automation(
        hashtag_interaction_manager=types.SimpleNamespace(stats_manager=_manager(4)))

    assert _finalize(monkeypatch, automation) == 4


def test_a_session_without_a_post_workflow_files_zero(monkeypatch):
    assert _finalize(monkeypatch, _automation()) == 0


def test_the_feed_runner_keeps_one_workflow_for_the_session(monkeypatch):
    """Each step used to build its own FeedBusiness: the count left with it."""
    built = []

    class _Feed:
        def __init__(self, *args):
            built.append(self)

        def interact_with_feed(self, config):
            return {'success': True}

    monkeypatch.setattr(
        "taktik.core.social_media.instagram.actions.business.workflows.feed.FeedBusiness", _Feed)
    automation = types.SimpleNamespace(
        device=None, session_manager=None,
        stats={'likes': 0, 'follows': 0, 'comments': 0, 'interactions': 0},
    )
    runner = WorkflowRunner(automation)

    runner._run_feed_workflow({'type': 'feed'})
    runner._run_feed_workflow({'type': 'feed'})

    assert len(built) == 1
    assert automation.feed_business is built[0]
