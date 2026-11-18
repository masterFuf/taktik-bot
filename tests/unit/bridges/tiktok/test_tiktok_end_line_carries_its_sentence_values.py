"""The `status` line that ends a TikTok run carries the values of its motive's sentence.

The app says why a run ended with the sentence of its code (« Limite de profils atteinte
({count}/{limit}) »). TikTok sent the code alone and the app showed the markers. Each bridge now
ends through `send_run_end`, which puts `reason_params` beside `completion_reason`, the way
Instagram's `session_stop` does.
"""

import logging
from types import SimpleNamespace

import pytest

from bridges.tiktok.automation import followers_events, post_url, sync_lists, target_profiles
from bridges.tiktok.common import ipc, video_callbacks
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.tiktok.workflows.automation.followers.models import FollowersStats
from taktik.core.social_media.tiktok.workflows.automation.sync_lists.models import SyncListsStats
from taktik.core.social_media.tiktok.workflows.automation.target_profiles import (
    TargetProfilesConfig,
    TargetProfilesWorkflow,
)
from taktik.core.social_media.tiktok.workflows.common.models import VideoWorkflowStats


@pytest.fixture(autouse=True)
def _clean_latch():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


@pytest.fixture
def lines(monkeypatch):
    sent = []

    def _send(event_type, **payload):
        sent.append({"type": event_type, **payload})

    monkeypatch.setattr(ipc, "send_message", _send)
    for module in (followers_events, post_url, sync_lists, target_profiles, video_callbacks):
        if hasattr(module, "send_message"):
            monkeypatch.setattr(module, "send_message", _send)
        monkeypatch.setattr(module, "send_status", lambda *a, **k: sent.append({"type": "status_plain"}),
                            raising=False)
    return sent


def _end_line(sent):
    ends = [line for line in sent if line["type"] == "status" and line.get("status") == "completed"]
    assert ends, f"no end line among {sent}"
    return ends[-1]


class _Repo:
    def end_session(self, **_kwargs):
        pass


def _target_workflow(usernames, max_profiles=50):
    workflow = TargetProfilesWorkflow.__new__(TargetProfilesWorkflow)
    workflow.config = TargetProfilesConfig(usernames=usernames, max_followers=max_profiles)
    workflow.logger = logging.getLogger("test.tiktok.end_line")
    workflow._followers_repository = _Repo()
    workflow._account_id = 1
    workflow._session_id = 2
    workflow._processed_usernames = set()
    workflow._paused = False
    workflow._running = True
    workflow._check_limits_reached = lambda: ""
    workflow._handle_popups = lambda *a, **k: False
    return workflow


def test_a_crashed_target_profiles_run_sends_the_error_text(lines):
    workflow = _target_workflow(["user_1"])

    def _crash():
        raise RuntimeError("screen gone")

    workflow._handle_popups = _crash
    stats = workflow.run(bot_username=None)
    target_profiles._send_final_stats(stats, ["user_1"])

    end = _end_line(lines)
    assert end["completion_reason"] == "crashed"
    assert end["reason_params"] == {"error": "screen gone"}


def test_a_profile_budget_reached_sends_count_and_limit(lines):
    workflow = _target_workflow(["user_1", "user_2"], max_profiles=0)
    stats = workflow.run(bot_username=None)
    target_profiles._send_final_stats(stats, ["user_1", "user_2"])

    end = _end_line(lines)
    assert end["completion_reason"] == "max_profiles_reached"
    assert end["reason_params"] == {"count": 0, "limit": 0}


def test_the_post_url_end_line_carries_the_values(lines):
    stats = FollowersStats(profiles_visited=3, likes=2, follows=1)
    stats.completion_reason = "completed"
    stats.completion_reason_params = {"interactions": 3}
    post_url._send_final_stats(stats)

    assert _end_line(lines)["reason_params"] == {"interactions": 3}


def test_the_followers_end_line_carries_the_session_values(lines):
    totals = {"profiles_visited": 4, "completion_reason": "max_likes_reached",
              "completion_reason_params": {"count": 5, "limit": 5}}
    followers_events.send_final_followers_stats(totals, 2)

    assert _end_line(lines)["reason_params"] == {"count": 5, "limit": 5}


def test_a_crashed_video_feed_sends_the_error_text(lines):
    stats = VideoWorkflowStats()
    stats.completion_reason = "crashed"
    stats.completion_reason_params = {"error": "screen gone"}
    video_callbacks.send_final_video_stats(stats, "For You")

    end = _end_line(lines)
    assert end["completion_reason"] == "crashed"
    assert end["reason_params"] == {"error": "screen gone"}


def test_the_sync_end_line_carries_the_values(lines):
    stats = SyncListsStats(rows_seen=12)
    stats.completion_reason = "list_exhausted"
    stats.completion_reason_params = {"seen": 12, "total": 12}
    sync_lists._send_final_stats(stats, "following")

    assert _end_line(lines)["reason_params"] == {"seen": 12, "total": 12}
