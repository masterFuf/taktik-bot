"""A row of the following list that hides its handle is never unfollowed, whatever the minimum age.

Without a handle the account can be neither dated, nor checked against a list, nor written to the
base once unfollowed. With no minimum age (the page's default) such a row used to be tapped like
any other. It is now kept, motive `handle_unknown`, in the events, the stats and the run log.
"""

import types

import pytest

import taktik.core.social_media.tiktok.actions.business.workflows.unfollow.workflow as workflow_module
from bridges.compat.diagnostics.actions.tiktok import ACTION_REGISTRY, register_actions


def test_a_row_without_a_handle_is_kept_without_a_minimum_age(screen, make_workflow, base_db):
    rows = [screen.Row("Hidden", None), screen.Row("Alpha", "alpha_one")]
    workflow = make_workflow(rows, min_follow_age_days=0)

    stats = workflow.run()

    assert [row.taps for row in rows] == [0, 1]
    assert ("skipped", None, "handle_unknown") in workflow.events
    assert stats.unfollowed == 1
    assert stats.skipped_handle_unknown == 1
    assert stats.to_dict()["refusals"] == {"handle_unknown": 1}
    assert stats.to_dict()["skipped_handle_unknown"] == 1
    assert base_db.recorded == [("alpha_one", 7)]


def test_a_row_without_a_handle_is_kept_under_its_own_motive_with_a_minimum_age(screen, make_workflow, base_db):
    rows = [screen.Row("Hidden", None)]
    workflow = make_workflow(rows, min_follow_age_days=3)

    stats = workflow.run()

    assert rows[0].taps == 0
    assert stats.refusals == {"handle_unknown": 1}
    assert stats.skipped_follow_date_unknown == 0
    assert base_db.looked_up == []


def test_a_list_of_rows_without_handles_ends_without_a_tap(screen, make_workflow, base_db):
    rows = [screen.Row("Hidden one", None), screen.Row("Hidden two", None)]
    workflow = make_workflow(rows, max_unfollows=5)

    stats = workflow.run()

    assert [row.taps for row in rows] == [0, 0]
    assert stats.unfollowed == 0
    assert stats.refusals == {"handle_unknown": 2}


def test_a_friends_row_without_a_handle_keeps_the_friends_motive(screen, make_workflow, base_db):
    rows = [screen.Row("Hidden", None, label="Ami(e)s")]
    workflow = make_workflow(rows)

    stats = workflow.run()

    assert rows[0].taps == 0
    assert stats.refusals == {"friends": 1}


@pytest.fixture
def lab(monkeypatch, clock, base_db):
    register_actions()

    class _Base:
        def __init__(self, device):
            self.device = device

        def _human_tap_bounds(self, element):
            return self.device.tap(element)

        def _find_and_click(self, *args, **kwargs):
            return True

    monkeypatch.setattr(workflow_module, "BaseAction", _Base)
    monkeypatch.setattr(workflow_module, "NavigationActions", lambda device: types.SimpleNamespace())
    monkeypatch.setattr(workflow_module, "ScrollActions", lambda device: types.SimpleNamespace())


def _bundle(phone):
    return types.SimpleNamespace(device=types.SimpleNamespace(_device=phone))


def test_the_lab_shows_and_applies_the_same_decision(lab, screen, base_db):
    rows = [screen.Row("Hidden", None)]
    phone = screen.FollowingList(rows)

    preview = ACTION_REGISTRY["tt.unfollow.preview_rows"](_bundle(phone), {"account": "moncompte"})
    one = ACTION_REGISTRY["tt.unfollow.unfollow_one"](_bundle(phone), {"account": "moncompte"})

    assert [(row["handle"], row["decision"]) for row in preview["details"]["rows"]] == [(None, "handle_unknown")]
    assert one["success"] is False
    assert one["details"]["refusals"] == {"handle_unknown": 1}
    assert rows[0].taps == 0
