"""The end-of-run `stats` event says what the session row says: both come from the ledger.

Measured on a phone (2026-09-24, hashtag run on main): three real likes, the live counter at
1, 2, 3, the session row at `stats_likes = 3`, and the final `{"type": "stats"}` event at
`likes: 0`, which the run page then displayed. The event read `InstagramAutomation.stats`, a
tally only the unfollow, post URL and feed runners fed; the hashtag and target runners never
did. The event now reads the action ledger (`interactions`, one row per gesture), the table
the session row is aggregated from at finalisation.
"""

import time
import types

import taktik.core.social_media.instagram.workflows.support.workflow_helpers as helpers_module
from taktik.core.social_media.instagram.workflows.support.workflow_helpers import WorkflowHelpers

_ZERO_TALLY = {'likes': 0, 'follows': 0, 'unfollows': 0, 'comments': 0, 'interactions': 0,
               'skipped': 0, 'stories_viewed': 0, 'stories_liked': 0}


def _hashtag_run(db):
    """Three post likes and a comment on two authors, as the hashtag posts pass files them,
    plus a visit that engaged nobody. The run tally stays at zero, as a hashtag run leaves it."""
    account_id, _ = db.get_or_create_account('bot_account')
    session_id = db.create_session(account_id, 'run', 'hashtag', 'videoproduction')
    for author, kind in (('author_one', 'LIKE'), ('author_two', 'LIKE'), ('author_two', 'LIKE'),
                         ('author_one', 'COMMENT'), ('visited_only', 'PROFILE_VISIT')):
        assert db.record_interaction(account_id, author, kind, session_id=session_id)
    automation = types.SimpleNamespace(
        current_session_id=session_id,
        stats={**_ZERO_TALLY, 'start_time': time.time()},
    )
    return automation, session_id


def test_the_final_event_counts_the_likes_the_ledger_holds(db, monkeypatch):
    monkeypatch.setattr(helpers_module, "get_local_database", lambda: db)
    automation, _session_id = _hashtag_run(db)

    totals = WorkflowHelpers(automation).final_stats()

    assert totals['likes'] == 3
    assert totals['comments'] == 1
    assert totals['interactions'] == 2, "two authors engaged; a bare visit engages nobody"


def test_the_final_event_and_the_session_row_agree(db, monkeypatch):
    monkeypatch.setattr(helpers_module, "get_local_database", lambda: db)
    automation, session_id = _hashtag_run(db)
    helpers = WorkflowHelpers(automation)

    assert helpers.update_workflow_session(session_id, 'COMPLETED') is True
    totals = helpers.final_stats()
    row = db.get_session(session_id)

    assert (totals['likes'], totals['comments'], totals['follows']) == (
        row['stats_likes'], row['stats_comments'], row['stats_follows'])


def test_without_a_session_the_run_tally_is_all_there_is(monkeypatch):
    def _no_db():
        raise AssertionError("no session: the ledger is not read")

    monkeypatch.setattr(helpers_module, "get_local_database", _no_db)
    automation = types.SimpleNamespace(current_session_id=None,
                                       stats={**_ZERO_TALLY, 'unfollows': 4})

    assert WorkflowHelpers(automation).final_stats()['unfollows'] == 4


def test_the_bridge_sends_the_ledger_totals_not_the_run_tally(monkeypatch):
    """The bridge side of the chain: `send_instagram_workflow_final_stats` receives
    `automation.final_stats()`."""
    import bridges.instagram.automation.runtime.workflow as runtime
    import taktik.core.social_media.instagram.workflows.core.automation as automation_module

    sent = []

    class _Automation:
        def __init__(self, _device_manager):
            self.stats = dict(_ZERO_TALLY)

        def run_workflow(self):
            pass

        def final_stats(self):
            return {'likes': 3, 'follows': 0, 'comments': 0, 'unfollows': 0, 'interactions': 2}

    monkeypatch.setattr(automation_module, "InstagramAutomation", _Automation)
    monkeypatch.setattr(runtime, "send_instagram_workflow_final_stats", sent.append)
    monkeypatch.setattr(runtime, "send_instagram_session_config", lambda *a, **k: None)
    monkeypatch.setattr(runtime, "send_status", lambda *a, **k: None)
    monkeypatch.setattr(runtime, "send_log", lambda *a, **k: None)
    runner = runtime.InstagramAutomationRunner(
        config={'workflowType': 'hashtags', 'target': 'videoproduction'},
        device_manager=None, app_service=None, package_name=None,
        ai_enabled=False, ai_service=None, ai_config={}, language='fr',
    )
    monkeypatch.setattr(runner, "_prepare_runtime", lambda _config: None)

    assert runner.run() is True

    assert sent == [{'likes': 3, 'follows': 0, 'comments': 0, 'unfollows': 0, 'interactions': 2}]
