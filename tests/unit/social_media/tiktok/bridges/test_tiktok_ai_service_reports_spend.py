"""The TikTok AI service reports what it costs.

The provider emits `ai_spend` through the IPC it was built with, and both TikTok callers (the
profile hooks of the automation runs and the new-followers welcome pass) built it with
`ipc=None`: every TikTok qualification and comment was paid and never reached the cost ledger.
The bridge's own IPC is now the default.
"""

import bridges.tiktok.workflows.automation.runtime.ai as tiktok_ai
from bridges.tiktok.runtime.ipc import _ipc


def _capture(monkeypatch):
    seen = {}

    def _create(**kwargs):
        seen.update(kwargs)
        return True, object()

    monkeypatch.setattr(tiktok_ai, "create_ai_service", _create)
    return seen


def test_without_an_ipc_the_service_reports_through_the_bridge(monkeypatch):
    seen = _capture(monkeypatch)

    tiktok_ai.create_tiktok_ai_service(ai_config={"enabled": True}, ipc=None)

    assert seen["ipc"] is _ipc
    assert hasattr(seen["ipc"], "ai_spend")


def test_an_ipc_given_by_the_caller_is_kept(monkeypatch):
    seen = _capture(monkeypatch)
    mine = object()

    tiktok_ai.create_tiktok_ai_service(ai_config={"enabled": True}, ipc=mine)

    assert seen["ipc"] is mine
