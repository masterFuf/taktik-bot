"""The publication, the account flows and the tasks open the door of a run, as the other launchers do.

They did not: on a locked phone, a publication, a login or a story relay started, then failed on its
selectors a minute later where the motive was a locked phone. Each launcher now opens
`open_run_door` before the app is touched, and each bridge says the refusal on its coded `error`
line (`send_run_refusal`), the line the desktop translates.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List

import pytest

from taktik.core.shared.diagnostics import run_door

SERIAL = "emulator-5554"


def _never(*_args, **_kwargs):
    raise AssertionError("the run went on past a locked phone")


class _NeverApp:
    """An app lifecycle no refused run may touch."""

    package = "com.example.app"

    def is_running(self):
        _never()

    def restart(self):
        _never()


@pytest.fixture
def locked(monkeypatch):
    monkeypatch.setattr(run_door, "phone_locked_after_lift", lambda device_id: True)


@pytest.fixture
def lines(monkeypatch) -> List[Dict[str, Any]]:
    from bridges.common.ipc import IPC

    printed: List[Dict[str, Any]] = []
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **kwargs: printed.append({"type": msg_type, **kwargs}))
    return printed


def _media(tmp_path) -> str:
    path = tmp_path / "a.png"
    path.write_bytes(b"x")
    return str(path)


def _instagram_publish(tmp_path):
    from taktik.core.social_media.instagram.workflows.common.startup import InstagramRunPhone
    from taktik.core.social_media.instagram.workflows.publish.agent_handler import run_instagram_publish

    return run_instagram_publish({"mediaPaths": [_media(tmp_path)]}, device_id=SERIAL,
                                 connect=lambda _package_name: InstagramRunPhone(device_manager=None),
                                 workflow_factory=_never)


def _instagram_account(tmp_path):
    from taktik.core.social_media.instagram.workflows.account.agent_handler import (
        INSTAGRAM_ACCOUNT_LOGOUT_WORKFLOW_ID,
        run_instagram_account,
    )

    return run_instagram_account(INSTAGRAM_ACCOUNT_LOGOUT_WORKFLOW_ID, {}, device=object(), device_id=SERIAL,
                                 app=_NeverApp(), logout_workflow_factory=_never)


def _instagram_story_relay(tmp_path):
    from taktik.core.social_media.instagram.workflows.tasks.agent_handler import run_instagram_story_relay

    return run_instagram_story_relay({"source_username": "source"}, device_id=SERIAL, connect=_never,
                                     relay=_never)


def _tiktok_publish(tmp_path):
    from taktik.core.social_media.tiktok.workflows.publish.agent_handler import run_tiktok_publish

    return run_tiktok_publish({"localPath": _media(tmp_path)}, device=object(), device_id=SERIAL,
                              workflow_factory=_never)


def _tiktok_account(tmp_path):
    from taktik.core.social_media.tiktok.workflows.account.agent_handler import (
        TIKTOK_ACCOUNT_LOGOUT_WORKFLOW_ID,
        run_tiktok_account,
    )

    return run_tiktok_account(TIKTOK_ACCOUNT_LOGOUT_WORKFLOW_ID, {}, device=object(), device_id=SERIAL,
                              app=_NeverApp(), logout_workflow_factory=_never)


@pytest.mark.parametrize("launch", [_instagram_publish, _instagram_account, _instagram_story_relay,
                                    _tiktok_publish, _tiktok_account])
def test_a_locked_phone_refuses_the_run_before_the_app(locked, tmp_path, launch):
    with pytest.raises(run_door.PhoneLockedError) as refused:
        launch(tmp_path)

    assert refused.value.device_id == SERIAL


def _refusal(lines) -> List[Dict[str, Any]]:
    return [line for line in lines if line["type"] == "error" and line.get("error_code") == "PHONE_LOCKED"]


class _Connection:
    def __init__(self, *_args, **_kwargs):
        self.device = object()
        self.device_manager = None

    def connect(self):
        return True

    def disconnect(self):
        pass


def test_the_instagram_publish_bridge_says_the_refusal(locked, lines, monkeypatch, tmp_path):
    import bridges.instagram.publish.bridge as bridge

    monkeypatch.setattr(bridge, "ConnectionService", _Connection)
    publisher = bridge.InstagramPublishBridge.__new__(bridge.InstagramPublishBridge)
    publisher.config = {"deviceId": SERIAL, "mediaPaths": [_media(tmp_path)]}
    publisher.device_id = SERIAL
    publisher._connection = None

    assert publisher.run() == 1
    assert len(_refusal(lines)) == 1


def test_the_tiktok_publish_bridge_says_the_refusal(locked, lines, monkeypatch, tmp_path):
    import bridges.tiktok.publish.bridge as bridge

    monkeypatch.setattr(bridge, "ConnectionService", _Connection)
    publisher = bridge.TikTokPublishBridge.__new__(bridge.TikTokPublishBridge)
    publisher.config = {"deviceId": SERIAL, "localPath": _media(tmp_path)}
    publisher.device_id = SERIAL
    publisher._connection = None
    publisher._artifact_dir = None

    assert publisher.run() == 1
    assert len(_refusal(lines)) == 1


def test_the_task_bridge_says_the_refusal(locked, lines, monkeypatch):
    import bridges.instagram.tasks.bridge as bridge

    monkeypatch.setattr(bridge.TaskBridge, "_prepare_runtime_session", lambda self: object())
    monkeypatch.setattr(bridge.TaskBridge, "_restart_instagram", _never)

    code = bridge.TaskBridge({
        "deviceId": SERIAL, "taskId": "story_relay", "params": {"source_username": "source"},
    }).run()

    assert code == 1
    assert len(_refusal(lines)) == 1
    assert not [line for line in lines if line["type"] == "task_result"]


def _account_bridge(module: str, cls: str):
    bridge_module = sys.modules.get(module) or __import__(module, fromlist=[cls])
    bridge = getattr(bridge_module, cls).__new__(getattr(bridge_module, cls))
    bridge.config = {"deviceId": SERIAL, "workflowType": "logout"}
    bridge.device_id = SERIAL
    bridge.workflow_type = "logout"
    bridge.package_name = None
    bridge._app = _NeverApp()
    return bridge


@pytest.mark.parametrize("module, cls", [
    ("bridges.instagram.account.bridge", "AccountBridge"),
    ("bridges.tiktok.account.bridge", "TikTokAccountBridge"),
])
def test_the_account_bridges_say_the_refusal_and_nothing_after_it(locked, lines, module, cls):
    """The flows report any failure of theirs as an uncoded error: the refusal ends the bridge first."""
    bridge = _account_bridge(module, cls)

    with pytest.raises(SystemExit) as ended:
        bridge._run_logout(object())

    assert ended.value.code == 1
    assert len(_refusal(lines)) == 1
    assert [line for line in lines if line["type"] == "error"] == _refusal(lines)
