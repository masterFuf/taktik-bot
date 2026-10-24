"""A sync run closes its session, with the motive of its read.

The two syncs (`sync_following`, `sync_followers_following`) are one-shot runs: their step printed
`sync_complete` then set `session_finalized` itself, which stops the run's loop but neither prints
`session_stop` nor writes the end of the `sessions_unified` row. On the Pixel 3 (2026-09-28) the
bridge exited 0 and the row stayed `ACTIVE`. The step now ends the session through
`finalize_session`, like every other run: `completed` when the lists were read, the motive of the
list that was not (`following_list_unproven`, `followers_list_unproven`, `fans_list_unproven`,
`list_unavailable`, of the « failed » family) otherwise. A fans category that Instagram does not
serve is no list that was not read; one read short of the size it announces is. A second list read
in part (`read_unproven`, said by the read itself) did open: it ends on its own motive, never on
`list_unavailable`, which stays for a list that never showed its rows.

No screen here: the lists' reads are played by their results, as `sync_following_list`,
`sync_followers_list` and `scrape_non_followers_category` return them.
"""

import json
from types import SimpleNamespace

import pytest

from taktik.core.social_media.instagram.workflows.automation import workflow_runner as runner_module
from taktik.core.social_media.instagram.workflows.automation.workflow_runner import WorkflowRunner


def _following(success, seen=12, expected=12):
    return {"new_count": 2, "updated_count": 0, "stopped_early": False, "total_seen": seen,
            "expected": expected, "success": success}


def _fans(success):
    return {"non_followers_count": 3 if success else None, "mutuals_count": 4, "success": success,
            "read_failed": not success}


def _fans_not_served():
    """`scrape_non_followers_category` when our followers list proves the fans category not served
    (410 in French, 2026-10-24: « Comptes désactivés » alone above « Tous les followers »)."""
    return {"non_followers_count": None, "mutuals_count": 0, "success": False, "category_not_served": True}


def _fans_read_in_part():
    """`scrape_non_followers_category` when the category was read short of the size it announces
    (Pixel 6a, Instagram 447, 2026-10-24: 171 of 537)."""
    return {"non_followers_count": None, "mutuals_count": 0, "success": False, "read_unproven": True,
            "total_seen": 171, "expected": 537}


def _followers(success):
    return {"new_count": 1, "updated_count": 0, "total_seen": 30, "success": success}


def _followers_read_in_part():
    """`sync_followers_list` when the list opened and its read ended short of the tab's count."""
    return {"new_count": 6, "updated_count": 0, "total_seen": 6, "expected": 1265, "success": False,
            "read_unproven": True}


class _Helpers:
    def __init__(self, automation):
        self.automation = automation
        self.ends = []

    def finalize_session(self, status="COMPLETED", reason="Limits reached"):
        self.ends.append((status, getattr(reason, "code", reason)))
        self.automation.session_finalized = True


def _runner(following, fans=None, followers=None):
    unfollow = SimpleNamespace(
        sync_following_list=lambda config=None: following,
        scrape_non_followers_category=lambda: fans,
        sync_followers_list=lambda config=None: followers,
        device=SimpleNamespace(device=SimpleNamespace(press=lambda key: None)),
    )
    automation = SimpleNamespace(session_finalized=False, unfollow_business=unfollow, stats={})
    automation.helpers = _Helpers(automation)
    return WorkflowRunner(automation), automation


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    monkeypatch.setattr(runner_module.time, "sleep", lambda _s: None, raising=False)


@pytest.mark.parametrize("following, fans, end", [
    (_following(True), _fans(True), ("COMPLETED", "completed")),
    (_following(False, seen=0), _fans(True), ("INTERRUPTED", "following_list_unproven")),
    (_following(True), _fans(False), ("INTERRUPTED", "list_unavailable")),
    # Instagram serves no fans category: there was no list to read, the list did open.
    (_following(True), _fans_not_served(), ("COMPLETED", "completed")),
    (_following(False, seen=0), _fans_not_served(), ("INTERRUPTED", "following_list_unproven")),
    # The fans category read in part: its list did open, and its count is not proven
    (_following(True), _fans_read_in_part(), ("INTERRUPTED", "fans_list_unproven")),
    (_following(False, seen=175, expected=1265), _fans_read_in_part(), ("INTERRUPTED", "following_list_unproven")),
])
def test_the_following_sync_ends_its_session(following, fans, end):
    runner, automation = _runner(following, fans=fans)

    runner._run_sync_following_workflow({"type": "sync_following"})

    assert automation.helpers.ends == [end]
    assert automation.session_finalized is True


def test_a_fans_category_read_in_part_is_a_failed_list_without_a_count(capsys):
    runner, _automation = _runner(_following(True), fans=_fans_read_in_part())

    runner._run_sync_following_workflow({"type": "sync_following"})

    line = next(json.loads(out) for out in capsys.readouterr().out.splitlines()
                if out.startswith("{") and '"sync_complete"' in out)
    assert (line["success"], line["non_followers_count"]) == (False, None)


def test_a_fans_category_not_served_is_no_failed_list_and_no_count(capsys):
    """The page shows « fans non lus », and the scheduled node does not fail on a list that Instagram
    does not serve (`sync_complete.success`: every list was read)."""
    runner, _automation = _runner(_following(True), fans=_fans_not_served())

    runner._run_sync_following_workflow({"type": "sync_following"})

    line = next(json.loads(out) for out in capsys.readouterr().out.splitlines()
                if out.startswith("{") and '"sync_complete"' in out)
    assert (line["success"], line["non_followers_count"]) == (True, None)


@pytest.mark.parametrize("following, followers, end", [
    (_following(True), _followers(True), ("COMPLETED", "completed")),
    (_following(False, seen=0), _followers(True), ("INTERRUPTED", "following_list_unproven")),
    # The followers list never showed its rows: unavailable
    (_following(True), _followers(False), ("INTERRUPTED", "list_unavailable")),
    # It opened and its read proved nothing: its own motive, with its numbers
    (_following(True), _followers_read_in_part(), ("INTERRUPTED", "followers_list_unproven")),
    (_following(False, seen=175, expected=1265), _followers_read_in_part(),
     ("INTERRUPTED", "following_list_unproven")),
])
def test_the_full_sync_ends_its_session(following, followers, end):
    runner, automation = _runner(following, followers=followers)

    runner._run_sync_followers_following_workflow({"type": "sync_followers_following", "mode": "fast"})

    assert automation.helpers.ends == [end]
    assert automation.session_finalized is True
