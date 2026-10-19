"""A sync run closes its session, with the motive of its read.

The two syncs (`sync_following`, `sync_followers_following`) are one-shot runs: their step printed
`sync_complete` then set `session_finalized` itself, which stops the run's loop but neither prints
`session_stop` nor writes the end of the `sessions_unified` row. On the Pixel 3 (2026-09-28) the
bridge exited 0 and the row stayed `ACTIVE`. The step now ends the session through
`finalize_session`, like every other run: `completed` when the lists were read, the motive of the
list that was not (`following_list_unproven`, `list_unavailable`, both of the « failed » family)
otherwise.

No screen here: the lists' reads are played by their results, as `sync_following_list`,
`sync_followers_list` and `scrape_non_followers_category` return them.
"""

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


def _followers(success):
    return {"new_count": 1, "updated_count": 0, "total_seen": 30, "success": success}


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
])
def test_the_following_sync_ends_its_session(following, fans, end):
    runner, automation = _runner(following, fans=fans)

    runner._run_sync_following_workflow({"type": "sync_following"})

    assert automation.helpers.ends == [end]
    assert automation.session_finalized is True


@pytest.mark.parametrize("following, followers, end", [
    (_following(True), _followers(True), ("COMPLETED", "completed")),
    (_following(False, seen=0), _followers(True), ("INTERRUPTED", "following_list_unproven")),
    (_following(True), _followers(False), ("INTERRUPTED", "list_unavailable")),
])
def test_the_full_sync_ends_its_session(following, followers, end):
    runner, automation = _runner(following, followers=followers)

    runner._run_sync_followers_following_workflow({"type": "sync_followers_following", "mode": "fast"})

    assert automation.helpers.ends == [end]
    assert automation.session_finalized is True
