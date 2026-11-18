"""A list sync ends with the values of its motive's sentence (`completion_reason_params`)."""

import logging
from types import SimpleNamespace

from taktik.core.social_media.tiktok.workflows.automation.sync_lists.workflow import SyncListsWorkflow


def _sync(reason, rows_seen=12, new_count=5, updated_count=2):
    workflow = SyncListsWorkflow.__new__(SyncListsWorkflow)
    workflow.logger = logging.getLogger("test.tiktok.sync_end")
    workflow.config = SimpleNamespace(max_scrolls=30)
    workflow._resolve_account = lambda _username: True
    workflow._lists_to_sync = lambda: ["following"]

    def _one_list(_list_type):
        workflow.stats.rows_seen = rows_seen
        workflow.stats.new_count = new_count
        workflow.stats.updated_count = updated_count
        workflow.stats.completion_reason = reason
        return True

    workflow._sync_one_list = _one_list
    return workflow.run(bot_username="account_1")


def test_a_list_read_to_its_end_says_how_many_rows():
    assert _sync("list_exhausted").completion_reason_params == {"seen": 12, "total": 12}


def test_a_list_stopped_at_its_scroll_cap_says_the_cap_and_the_rows():
    assert _sync("max_scrolls_reached").completion_reason_params == {"scrolls": 30, "seen": 12}


def test_a_list_stopped_on_a_known_handle_says_the_streak_and_the_rows():
    assert _sync("known_reached").completion_reason_params == {"streak": 1, "seen": 12}


def test_a_completed_sync_counts_the_rows_it_wrote():
    assert _sync("").completion_reason_params == {"interactions": 7}
