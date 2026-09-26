"""Gmail and YouTube: the bridge and the CLI handler reach the workflow through the same launcher.

The bridges used to build `GmailWorkflow`, `YouTubeAccountWorkflow` and `YouTubeUploadWorkflow`
themselves, next to handlers that built them too. Each host still reads its own payload and
emits its own events; the engine is built and called in one place, `run_*` of the handler module.
"""
from __future__ import annotations

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowRegistry

DEVICE = object()
DEVICE_ID = "emulator-5554"


class Recorder:
    def __init__(self):
        self.calls: list[tuple] = []


def _silent(*_args, **_kwargs):
    return None


# --------------------------------------------------------------------------- Gmail


def _fake_gmail(recorder):
    class FakeGmailWorkflow:
        def __init__(self, device, device_id, notifier=None):
            recorder.calls.append(("built", device is DEVICE, device_id))

        def ensure_account_added(self, email, password):
            recorder.calls.append(("ensure_account_added", email, password))
            return {"success": True, "message": "added"}

        def scan_accounts(self):
            recorder.calls.append(("scan_accounts",))
            return {"success": True, "accounts": [{"email": "a@example.com"}], "message": "1"}

    return FakeGmailWorkflow


def _gmail_handler(workflow_id, params, factory, persisted):
    from taktik.core.app.email.gmail.workflows.agent_handler import register_gmail_account_handlers

    registry = WorkflowRegistry()
    register_gmail_account_handlers(registry, device=DEVICE, device_id=DEVICE_ID,
                                    account_persister=persisted.append, workflow_factory=factory)
    invocation = WorkflowInvocation(platform="gmail", workflow_id=workflow_id, params=params)
    return registry.resolve(workflow_id)(invocation, {})


def test_gmail_login_is_the_same_call_from_the_bridge_and_the_cli(monkeypatch):
    from bridges.gmail.account.runtime import workflow_login
    from taktik.core.app.email.gmail.workflows import agent_handler

    bridge, cli = Recorder(), Recorder()
    bridge_saved: list[str] = []
    monkeypatch.setitem(agent_handler.run_gmail_account.__kwdefaults__, "workflow_factory", _fake_gmail(bridge))
    monkeypatch.setattr(workflow_login, "persist_gmail_account", lambda email, *_: bridge_saved.append(email))
    exit_code = workflow_login.run_gmail_login(
        config={"email": "a@example.com", "password": "secret"}, device=DEVICE, device_id=DEVICE_ID,
        notifier=None, send_status=_silent, send_log=_silent, send_error=_silent, send_message=_silent,
    )

    cli_saved: list[str] = []
    _gmail_handler("gmail.account.login", {"email": "a@example.com", "password": "secret"},
                   _fake_gmail(cli), cli_saved)

    assert exit_code == 0
    assert bridge.calls == cli.calls == [
        ("built", True, DEVICE_ID), ("ensure_account_added", "a@example.com", "secret"),
    ]
    assert bridge_saved == cli_saved == ["a@example.com"]


def test_gmail_scan_persists_the_same_accounts_from_both_hosts(monkeypatch):
    from bridges.gmail.account.runtime import workflow_scan
    from taktik.core.app.email.gmail.workflows import agent_handler

    bridge, cli = Recorder(), Recorder()
    bridge_saved: list[str] = []
    monkeypatch.setitem(agent_handler.run_gmail_account.__kwdefaults__, "workflow_factory", _fake_gmail(bridge))
    monkeypatch.setattr(workflow_scan, "persist_gmail_account", lambda email, *_: bridge_saved.append(email))
    workflow_scan.run_gmail_scan_accounts(
        device=DEVICE, device_id=DEVICE_ID, notifier=None,
        send_status=_silent, send_log=_silent, send_error=_silent, send_message=_silent,
    )
    cli_saved: list[str] = []
    _gmail_handler("gmail.account.scan_accounts", {}, _fake_gmail(cli), cli_saved)

    assert bridge.calls == cli.calls
    assert bridge_saved == cli_saved == ["a@example.com"]


# --------------------------------------------------------------------------- YouTube


def _fake_upload(recorder):
    class FakeYouTubeUploadWorkflow:
        def __init__(self, device, device_id):
            recorder.calls.append(("built", device is DEVICE, device_id))

        def execute(self, **params):
            recorder.calls.append(("execute", tuple(sorted(params.items()))))
            return {"success": True, "message": "uploaded"}

    return FakeYouTubeUploadWorkflow


def test_youtube_upload_is_the_same_call_from_the_bridge_and_the_cli(monkeypatch, tmp_path):
    from bridges.youtube.publish.runtime.request import build_upload_request
    from bridges.youtube.publish.runtime.workflow import run_youtube_upload_workflow
    from taktik.core.social_media.youtube.workflows.publish import agent_handler

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    page = {"deviceId": DEVICE_ID, "localPath": str(video), "title": "Hello",
            "description": "d", "uploadType": "short", "visibility": "Public"}

    bridge, cli = Recorder(), Recorder()
    monkeypatch.setitem(agent_handler.run_youtube_upload.__kwdefaults__, "workflow_factory", _fake_upload(bridge))
    request = build_upload_request(page, 100, _silent, _silent)
    exit_code = run_youtube_upload_workflow(device=DEVICE, device_id=DEVICE_ID, request=request,
                                            send_status=_silent, send_message=_silent,
                                            send_error=_silent, send_log=_silent)

    registry = WorkflowRegistry()
    agent_handler.register_youtube_publish_handlers(registry, device=DEVICE, device_id=DEVICE_ID,
                                                    workflow_factory=_fake_upload(cli))
    invocation = WorkflowInvocation(platform="youtube", workflow_id=agent_handler.YOUTUBE_UPLOAD_POST_WORKFLOW_ID,
                                    params=page)
    registry.resolve(agent_handler.YOUTUBE_UPLOAD_POST_WORKFLOW_ID)(invocation, {})

    assert exit_code == 0
    assert bridge.calls == cli.calls


def test_youtube_login_is_the_same_call_from_the_bridge_and_the_cli(monkeypatch):
    from bridges.youtube.account.runtime import workflows as bridge_workflows
    from taktik.core.social_media.youtube.workflows.account import agent_handler

    def fake(recorder):
        class FakeYouTubeAccountWorkflow:
            def __init__(self, device, device_id, *, notifier=None, account_repository=None):
                recorder.calls.append(("built", device is DEVICE, device_id, account_repository))

            def login(self, *, email, password=""):
                recorder.calls.append(("login", email, password))
                return {"success": True, "message": "ok"}

        return FakeYouTubeAccountWorkflow

    bridge, cli = Recorder(), Recorder()
    monkeypatch.setitem(agent_handler.run_youtube_account.__kwdefaults__, "workflow_factory", fake(bridge))
    for name in ("send_status", "send_message", "send_error", "send_log"):
        monkeypatch.setattr(bridge_workflows, name, _silent)
    bridge_workflows.run_youtube_account_login({"email": "a@example.com", "password": "pw"},
                                               device=DEVICE, device_id=DEVICE_ID)

    registry = WorkflowRegistry()
    agent_handler.register_youtube_account_handlers(registry, device=DEVICE, device_id=DEVICE_ID,
                                                    workflow_factory=fake(cli))
    invocation = WorkflowInvocation(platform="youtube", workflow_id=agent_handler.YOUTUBE_ACCOUNT_LOGIN_WORKFLOW_ID,
                                    params={"email": "a@example.com", "password": "pw"})
    registry.resolve(agent_handler.YOUTUBE_ACCOUNT_LOGIN_WORKFLOW_ID)(invocation, {})

    assert bridge.calls == cli.calls == [("built", True, DEVICE_ID, None), ("login", "a@example.com", "pw")]
