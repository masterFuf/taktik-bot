"""A story relay whose Instagram does not restart stops, and says why (decision Q17 of 2026-09-27).

The task bridge called `AppService.restart()` and dropped its answer: when Instagram did not come
back, the relay went on from whatever screen the phone showed, and a failure read as "no story".
The launcher now stops the pass before the relay, for every host (the bridge and the CLI), with
the reason the shared Instagram startup uses for the same fact.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from taktik.core.social_media.instagram.workflows.core.agent_handler import InstagramStartError
from taktik.core.social_media.instagram.workflows.tasks import agent_handler
from taktik.core.social_media.instagram.workflows.tasks.story_relay import INSTAGRAM_LAUNCH_FAILED


def _relay_never_called(**_kwargs):
    raise AssertionError("the relay ran although Instagram did not restart")


def test_the_launcher_stops_the_pass_when_instagram_does_not_start():
    def connect(_package_name):
        raise InstagramStartError("Instagram did not start cleanly; the task was not started")

    report = agent_handler.run_instagram_story_relay(
        {"source_username": "@source_account"}, connect=connect, relay=_relay_never_called,
    )

    assert report["success"] is False
    assert report["reason"] == INSTAGRAM_LAUNCH_FAILED
    assert report["source_username"] == "source_account"
    assert report["relayed"] == 0 and report["outcomes"] == []


@pytest.fixture
def lines(monkeypatch) -> List[Dict[str, Any]]:
    from bridges.common.ipc import IPC

    printed: List[Dict[str, Any]] = []
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **kwargs: printed.append({"type": msg_type, **kwargs}))
    return printed


def test_the_task_bridge_reports_a_failed_restart(monkeypatch, lines):
    import bridges.instagram.tasks.bridge as bridge

    class _AppThatDoesNotStart:
        def __init__(self, *_args, **_kwargs):
            pass

        def restart(self) -> bool:
            return False

    monkeypatch.setattr(bridge, "AppService", _AppThatDoesNotStart)
    monkeypatch.setattr(bridge.TaskBridge, "_prepare_runtime_session", lambda self: object())
    monkeypatch.setitem(agent_handler.run_instagram_story_relay.__kwdefaults__, "relay", _relay_never_called)

    code = bridge.TaskBridge({
        "deviceId": "emulator-5554", "taskId": "story_relay", "params": {"source_username": "source_account"},
    }).run()

    assert code == 1
    results = [line for line in lines if line["type"] == "task_result"]
    assert len(results) == 1
    assert results[0]["success"] is False
    assert results[0]["report"]["reason"] == INSTAGRAM_LAUNCH_FAILED
    assert {"type": "status", "status": "error", "message": INSTAGRAM_LAUNCH_FAILED} in [
        {key: line.get(key) for key in ("type", "status", "message")} for line in lines if line["type"] == "status"
    ]
