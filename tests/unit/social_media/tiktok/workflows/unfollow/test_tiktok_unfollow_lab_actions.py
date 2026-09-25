"""The Cartography Lab covers the TikTok unfollow's screen steps, through the production workflow.

`tt.unfollow.preview_rows` reads the decision the run would take for each visible row;
`tt.unfollow.unfollow_one` runs one pass of the production `process_rows` (decision, tap, proof by
the row, record). Rule of Kevin: every screen capability is testable on its own from the Lab, on
the same function as production. Same fake list as the workflow tests (conftest.py).
"""

import types

import pytest

import taktik.core.social_media.tiktok.actions.business.workflows.unfollow.workflow as workflow_module
from bridges.compat.diagnostics.actions.tiktok import ACTION_REGISTRY, register_actions


@pytest.fixture
def lab(monkeypatch, screen, clock, base_db):
    """A Lab bundle on the fake list. Only the taps and the navigation helpers are stand-ins."""
    register_actions()

    phones = []

    class _Base:
        def __init__(self, device):
            phones.append(device)
            self.device = device

        def _human_tap_bounds(self, element):
            return self.device.tap(element)

        def _find_and_click(self, *args, **kwargs):
            return True

    monkeypatch.setattr(workflow_module, "BaseAction", _Base)
    monkeypatch.setattr(workflow_module, "NavigationActions", lambda device: types.SimpleNamespace())
    monkeypatch.setattr(workflow_module, "ScrollActions", lambda device: types.SimpleNamespace())
    return phones


def _bundle(phone):
    return types.SimpleNamespace(device=types.SimpleNamespace(_device=phone))


def test_preview_rows_reads_the_decisions_without_tapping(lab, screen, base_db):
    base_db.ages.update({"old": 10})
    rows = [screen.Row("Old", "old"), screen.Row("Hand", "by_hand"), screen.Row("Beta", "beta", label="Ami(e)s")]
    phone = screen.FollowingList(rows)

    result = ACTION_REGISTRY["tt.unfollow.preview_rows"](
        _bundle(phone), {"account": "moncompte", "min_follow_age_days": 3})

    decisions = {row["handle"]: (row["state"], row["decision"]) for row in result["details"]["rows"]}
    assert decisions == {
        "old": ("following", "unfollow"),
        "by_hand": ("following", "follow_date_unknown"),
        "beta": ("friends", "friends"),
    }
    assert [row.taps for row in rows] == [0, 0, 0]


def test_unfollow_one_goes_through_the_production_steps(lab, screen, base_db):
    rows = [screen.Row("Alpha", "alpha_one"), screen.Row("Gamma", "gamma")]
    phone = screen.FollowingList(rows)

    result = ACTION_REGISTRY["tt.unfollow.unfollow_one"](_bundle(phone), {"account": "moncompte", "username": "gamma"})

    assert result["success"] is True
    assert [row.taps for row in rows] == [0, 1]
    assert base_db.recorded == [("gamma", 7)]
    assert result["details"]["unfollowed"] == 1


def test_unfollow_one_reports_a_tap_the_row_did_not_confirm(lab, screen, base_db):
    rows = [screen.Row("Alpha", "alpha_one", on_tap=screen.STAY)]

    result = ACTION_REGISTRY["tt.unfollow.unfollow_one"](
        _bundle(screen.FollowingList(rows)), {"account": "moncompte"})

    assert result["success"] is False
    assert result["details"]["unconfirmed"] == 1
    assert base_db.recorded == []


def test_unfollow_one_taps_a_single_row_even_when_the_row_does_not_confirm(lab, screen, base_db):
    # An unconfirmed tap may still have unfollowed: the action promises ONE account, so it must
    # not move on to the next rows as the production run does (3 unconfirmed in a row).
    rows = [screen.Row(name, name.lower(), on_tap=screen.STAY) for name in ("Alpha", "Beta", "Gamma")]

    ACTION_REGISTRY["tt.unfollow.unfollow_one"](_bundle(screen.FollowingList(rows)), {"account": "moncompte"})

    assert [row.taps for row in rows] == [1, 0, 0]


def test_unfollow_one_refuses_without_the_account(lab, screen):
    rows = [screen.Row("Alpha", "alpha_one")]

    result = ACTION_REGISTRY["tt.unfollow.unfollow_one"](_bundle(screen.FollowingList(rows)), {})

    assert result["success"] is False
    assert rows[0].taps == 0
