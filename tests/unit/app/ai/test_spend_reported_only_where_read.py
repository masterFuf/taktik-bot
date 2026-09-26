"""`ai_spend` leaves the bridge only for runs whose session reads it.

Four runs are read by the desktop and store their cost in the run's session: Instagram
automation, TikTok automation and followers, Instagram cold DM, TikTok DM outreach. Four others
emitted it with nothing on the other end: Instagram scraping, the Taktik Agent, the Instagram
notifications pass and the TikTok welcome pass. An event emitted without a reader is removed
(anti-drift rule 4); their services keep their IPC for the Agent cards.
"""

import json
import urllib.request

from taktik.core.app.ai.factory import build_ai_service


class _RecordingIpc:
    def __init__(self):
        self.events = []

    def ai_spend(self, cost_usd, model=None, label=None, kind="other"):
        self.events.append(("ai_spend", cost_usd, kind))


class _Resp:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    @staticmethod
    def read():
        return json.dumps({
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "model": "qwen/qwen3.7-flash",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.0004},
        }).encode()


def _spent(service, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda _request, **_kw: _Resp())
    result = service._call_openrouter("qwen/qwen3.7-flash", [], label="t", kind="profile")
    assert result["success"] is True
    return service.ipc.events


def test_a_service_that_reports_spend_still_does(monkeypatch):
    service = build_ai_service(api_key="x" * 10, ipc=_RecordingIpc())
    assert _spent(service, monkeypatch) == [("ai_spend", 0.0004, "profile")]


def test_a_service_built_without_spend_reporting_keeps_its_ipc_and_emits_none(monkeypatch):
    ipc = _RecordingIpc()
    service = build_ai_service(api_key="x" * 10, ipc=ipc, report_spend=False)
    assert service.ipc is ipc
    assert _spent(service, monkeypatch) == []


def test_scraping_and_agent_services_report_no_spend(monkeypatch):
    from bridges.instagram.agent.runtime.ai import build_agent_ai_service
    from bridges.instagram.scraping.runtime.ai import build_scraping_ai_service

    for build in (build_scraping_ai_service, build_agent_ai_service):
        ipc = _RecordingIpc()
        service = build(api_key="x" * 10, ipc=ipc)
        assert service.ipc is ipc
        assert _spent(service, monkeypatch) == []


def _capture_create(monkeypatch, module):
    seen = {}

    def _create(**kwargs):
        seen.update(kwargs)
        return False, None

    monkeypatch.setattr(module, "create_ai_service", _create)
    return seen


def test_the_instagram_notifications_pass_reports_no_spend(monkeypatch):
    import bridges.instagram.runtime.ai as instagram_ai
    from bridges.instagram.engagement.runtime.notifications.ai import install_notifications_ai_hooks

    seen = _capture_create(monkeypatch, instagram_ai)
    install_notifications_ai_hooks(ai_config={"enabled": True}, device=object())

    assert seen["report_spend"] is False


def test_the_instagram_automation_still_reports_spend(monkeypatch):
    import bridges.instagram.runtime.ai as instagram_ai

    seen = _capture_create(monkeypatch, instagram_ai)
    instagram_ai.create_instagram_ai_service(ai_config={"enabled": True}, ipc=object(), log=lambda *_: None)

    assert seen.get("report_spend", True) is True


def test_the_tiktok_welcome_pass_reports_no_spend_and_automation_does(monkeypatch):
    import bridges.tiktok.workflows.automation.runtime.ai as tiktok_ai

    seen = _capture_create(monkeypatch, tiktok_ai)
    assert tiktok_ai.build_welcome_qualifier({"enabled": True}, "en") is None
    assert seen["report_spend"] is False

    seen.clear()
    tiktok_ai.create_tiktok_ai_service(ai_config={"enabled": True})
    assert seen.get("report_spend", True) is True
