"""The Instagram bridges read the file the contract describes and print the lines it declares.

As for the TikTok bridges (`test_workflow_contract_bridges.py`): the whole bridge runs, from its
config file to its stdout, on the app's file; only what touches the phone, the network or the base
is replaced. The lines are printed by the production emitters the workflow calls (`IPCEmitter`, the
IPC's AI helpers, the workflow's own announcements), not written by the test.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from contract_probe import DEVICE, Recording, lookup, merge, probe
from taktik.core.app.contract.instagram_engagement import INSTAGRAM_COLD_DM, INSTAGRAM_DM_READ, INSTAGRAM_DM_SEND
from taktik.core.app.contract.instagram_scraping import INSTAGRAM_SCRAPING, SCRAPING_TYPES
from taktik.core.app.contract.schema import Shape, WorkflowContract, has_default, nested_fields
from test_workflow_contract_bridges import check_lines, declared_paths, file_paths, no_ip_rotation  # noqa: F401


def _value(item) -> Any:
    return item.default if has_default(item) and not isinstance(item.default, tuple) else probe(item)


def _holds(when, data) -> bool:
    """`data` holds what `when` asks (a tuple: any of its values)."""
    for dotted, wanted in when.items():
        present, value = lookup(data, tuple(dotted.split(".")))
        if not present or not (value in wanted if isinstance(wanted, tuple) else value == wanted):
            return False
    return True


def app_file(contract: WorkflowContract, **chosen: Any) -> Dict[str, Any]:
    """The file the app writes for these choices: every setting read under them, at its wire key.

    `chosen` fixes the settings the others depend on (`type`, `deepQualify`, `ai.enabled`); a host
    field (the AI key, the session's account) is in the file: the main process fills it."""
    data: Dict[str, Any] = merge(chosen)
    for path, item, when, _ in nested_fields(contract.settings):
        if isinstance(item.type, Shape) or not item.app or not _holds(when, data):
            continue
        if path[:-1] and not lookup(data, path[:-1])[0]:
            continue
        holder = data
        for key in path[:-1]:
            holder = holder[key]
        holder.setdefault(item.key, _value(item))
    for item in contract.bridge_fields:
        data[item.key] = BRIDGE_VALUES[item.key]
    return data


#: What the main process writes for the bridge's own fields.
BRIDGE_VALUES = {
    "deviceId": DEVICE,
    "packageName": "com.instagram.android",
    "networkReset": {"enabled": True, "method": "data"},
}


def assert_reads(contract: WorkflowContract, data: Dict[str, Any], log: set) -> None:
    unread = file_paths(data) - log
    undeclared = log - declared_paths(contract)
    assert not unread, f"keys of the file nobody reads: {sorted(unread)}"
    assert not undeclared, f"keys read and not declared: {sorted(undeclared)}"


@pytest.fixture
def printed(monkeypatch, capsys):
    """Every JSON line the bridge prints: through the IPC, and the ones it prints itself."""
    from bridges.common.runtime.ipc import IPC

    sent: List[Dict[str, Any]] = []
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **kwargs: sent.append({"type": msg_type, **kwargs}))

    def lines() -> List[Dict[str, Any]]:
        out = []
        for line in capsys.readouterr().out.splitlines():
            line = line.strip()
            if line.startswith("{"):
                out.append(json.loads(line))
        return sent + out

    return lines


# ------------------------------------------------------------------------------------ scraping


class _Db:
    def create_scraping_session(self, **kwargs):
        return 7

    def update_scraped_profile_ai(self, *args, **kwargs):
        return None

    def update_profile_city(self, *args, **kwargs):
        return None


class _Ai:
    model_analysis = "qwen"

    def __init__(self):
        self.answers = [
            {"success": True, "text": '{"score": 8, "qualified": true, "reason": "bakes"}', "model": "qwen",
             "cost_usd": 0.0004},
            {"success": False, "error": "rate limited"},
        ]

    def text_completion(self, *args, **kwargs):
        return self.answers.pop(0)


def _scraping_class():
    from loguru import logger

    from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter
    from taktik.core.social_media.instagram.workflows.scraping.scraping_workflow import ScrapingWorkflow

    class Scraping(ScrapingWorkflow):
        """The production workflow's emitters; only the walk of the screens is left out."""

        def __init__(self, device_manager, config, ai_notifier=None, ai_service=None, ai_service_factory=None):
            self.device_manager = device_manager
            self.device = device_manager.device
            self.config = config
            self.logger = logger.bind(module="scraping-workflow")
            self.local_db = _Db()
            self._ipc = ai_notifier
            self._ai_service = _Ai()
            self.scraped_posts = []
            self.scraping_session_id = None

        def _read_post_counts(self):
            return 120, None

        def run(self):
            profile = {"username": "bob", "full_name": "Bob", "biography": "Baker", "followers_count": 340,
                       "following_count": 12, "posts_count": 9, "is_private": False, "is_verified": False,
                       "is_business": True, "business_category": "Bakery"}
            self._create_scraping_session()
            self._announce_target_info("alice", 1200, 3, "followers")
            IPCEmitter.emit_scraping_profile_visit("bob", profile)
            IPCEmitter.emit_scraping_dq_progress("bob", 5, 30)
            IPCEmitter.emit_profile_skipped("carol", "already_processed")
            IPCEmitter.emit_profile_captured("bob", profile, profile_pic_base64="data:image/jpeg;base64,AAAA")
            self._announce_post_url("https://www.instagram.com/p/AbC1/", "cuisine")
            self._collect_open_post("alice", None, set())
            self._qualify_profile_ai(profile, 1)
            self._qualify_profile_ai(dict(profile, username="dave"), 2)
            return {"success": True, "total_scraped": 1, "completion_reason": "completed"}

    return Scraping


@pytest.fixture
def scraping_bridge(monkeypatch):
    import sys

    import bridges.instagram.runtime.ipc as ipc_adapter
    import bridges.instagram.scraping.runtime.runner as runner
    from taktik.core.social_media.instagram.actions.core.ipc import emitter
    from taktik.core.social_media.instagram.workflows.core import runtime_setup
    from taktik.core.social_media.instagram.workflows.scraping import agent_handler, profile_posts_scraping

    device_manager = SimpleNamespace(device=object())
    monkeypatch.setattr(runner, "configure_scraping_database", lambda: None)
    monkeypatch.setattr(runner, "create_scraping_connection", lambda device_id: SimpleNamespace())
    monkeypatch.setattr(runner, "connect_scraping_device", lambda connection: device_manager)
    monkeypatch.setattr(runner, "disconnect_scraping_connection", lambda connection: None)
    monkeypatch.setattr(runner, "scraping_installed_version", lambda connection, package: lambda: "410.0.0.53.71")
    monkeypatch.setattr(runtime_setup, "prepare_instagram_selectors", lambda **kwargs: None)
    monkeypatch.setattr(agent_handler, "_default_workflow_factory", _scraping_class)
    monkeypatch.setattr(profile_posts_scraping, "get_post_url_from_share",
                        lambda device, log: "https://www.instagram.com/p/Post1/")
    monkeypatch.setattr(emitter, "_bridge_adapter", sys.modules[ipc_adapter.__name__])
    return runner


@pytest.mark.parametrize("kind", SCRAPING_TYPES)
def test_the_scraping_bridge_follows_its_contract(scraping_bridge, printed, kind):
    data = app_file(INSTAGRAM_SCRAPING, type=kind, deepQualify=True,
                    ai={"enabled": True, "qualificationPrompt": "Bakers only"})
    log: set = set()

    assert scraping_bridge.ScrapingRun(Recording(data, log)).run() == 0

    assert_reads(INSTAGRAM_SCRAPING, data, log)
    lines = printed()
    check_lines(INSTAGRAM_SCRAPING, lines)
    assert {line["type"] for line in lines} == {event.type for event in INSTAGRAM_SCRAPING.events}


def test_a_scraping_run_with_nothing_to_scrape_is_refused_in_its_last_line(scraping_bridge, printed):
    data = app_file(INSTAGRAM_SCRAPING, type="hashtag")
    data["hashtags"] = []

    assert scraping_bridge.ScrapingRun(data).run() == 1

    lines = printed()
    check_lines(INSTAGRAM_SCRAPING, lines)
    assert [line["type"] for line in lines] == ["scraping_result"]
    assert lines[0]["success"] is False and "hashtags" in lines[0]["error"]


# ------------------------------------------------------------------------------------- cold DM


class _Response:
    """What OpenRouter answers a generation: the text and its cost."""

    def __init__(self, *args, **kwargs):
        self.body = json.dumps({
            "model": "qwen", "choices": [{"message": {"content": "Hello there"}, "finish_reason": "stop"}],
            "usage": {"cost": 0.0003, "prompt_tokens": 40, "completion_tokens": 6},
        }).encode("utf-8")

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _cold_dm_class():
    from taktik.core.social_media.instagram.workflows.cold_dm import workflow

    class ColdDm(workflow.ColdDMWorkflow):
        """The production workflow; only what it asks of the phone and of the base answers here."""

        def filter_pending_recipients(self, recipients, account_id):
            return list(recipients)

        def _detect_app_language(self):
            return None

        def go_home(self):
            return None

        def reach_and_send(self, recipient, compose, policy=None):
            return {"outcome": workflow.SENT, "message": compose(), "send_result": True}

    return ColdDm


@pytest.fixture
def cold_dm_bridge(monkeypatch, no_ip_rotation):
    import urllib.request

    import bridges.instagram.engagement.runtime.cold_dm.commands as bridge
    import taktik.core.database.local.service as local
    from taktik.core.social_media.instagram.workflows.cold_dm import agent_handler, workflow

    connection = SimpleNamespace(connect=lambda: True, device=object(), device_manager=object(), restart=lambda: None)
    monkeypatch.setattr(bridge, "KeyboardService", lambda device_id: object())
    monkeypatch.setattr(bridge, "InstagramBridgeBase", lambda device_id, package_name=None: connection)
    monkeypatch.setattr(agent_handler, "_default_workflow_factory", _cold_dm_class)
    monkeypatch.setattr(workflow, "apply_cold_dm_send_result",
                        lambda *, workflow, **kwargs: setattr(workflow, "dms_sent", workflow.dms_sent + 1))
    monkeypatch.setattr(workflow, "wait_before_next_cold_dm", lambda **kwargs: None)
    monkeypatch.setattr(local, "get_local_database", lambda: SimpleNamespace(
        create_session=lambda **kwargs: 11, finalize_session=lambda *args, **kwargs: None))
    monkeypatch.setattr(urllib.request, "urlopen", _Response)
    return bridge


def test_the_cold_dm_bridge_follows_its_contract(cold_dm_bridge, printed):
    data = app_file(INSTAGRAM_COLD_DM, messageMode="ai", aiPrompt="Say hello", openrouterApiKey="sk-test",
                    sessionAccountId=3)
    log: set = set()

    assert cold_dm_bridge.ColdDmRun(Recording(data, log)).run() == 0

    assert_reads(INSTAGRAM_COLD_DM, data, log)
    lines = printed()
    check_lines(INSTAGRAM_COLD_DM, lines)
    assert {line["type"] for line in lines} == {event.type for event in INSTAGRAM_COLD_DM.events}
    assert lines[-1]["type"] == "cold_dm_result" and lines[-1]["success"] is True


def test_a_cold_dm_without_a_message_is_refused_in_its_last_line(cold_dm_bridge, printed):
    data = app_file(INSTAGRAM_COLD_DM, messageMode="manual", messages=[])

    with pytest.raises(SystemExit):
        cold_dm_bridge.ColdDmRun(data).run()

    lines = printed()
    check_lines(INSTAGRAM_COLD_DM, lines)
    assert [line["type"] for line in lines] == ["cold_dm_result"]
    assert lines[0]["success"] is False


# ------------------------------------------------------------------------------------ DM inbox


def _dm_class():
    import bridges.instagram.engagement.runtime.dm.bridge as dm_bridge
    from taktik.core.social_media.instagram.workflows.dm_inbox.conversation_payload import (
        build_answered_conversation,
        build_conversation_payload,
        build_up_to_date_conversation,
    )

    class Dm(dm_bridge.DMBridge):
        """The bridge's runtime and its announcements; only the walk of the inbox answers here."""

        device = None
        _dm_account_username = "acting"

        def connect(self):
            return True

        def restart_instagram(self):
            return None

        def navigate_to_dm_inbox(self):
            return True

        def open_requests_folder(self):
            return True

        def _reset_inbox_to_top(self, strategy="auto"):
            return None

        def open_conversation(self, username):
            return True

        def send_message(self, message):
            return True

        def read_conversations(self, limit):
            read = build_conversation_payload(
                real_username="alice", inbox_username="alice", is_group=False, can_reply=True,
                messages=[{"type": "text", "text": "Hi", "is_sent": False, "timestamp": "10:02"},
                          {"type": "reel", "text": "[Reel]", "is_sent": False, "reaction": "like"}])
            answered = build_answered_conversation(real_username="bob", inbox_username="bob")
            known = build_up_to_date_conversation(real_username="carol", inbox_username="carol", last_is_ours=False)
            self._announce_conversation(read, current=1, total=limit)
            self._announce_conversation(answered, current=2, total=limit)
            self._announce_conversation(known, current=3, total=limit)
            self._announce_up_to_date("carol", answered=False, current=3, total=limit)
            return [read, answered, known]

    return Dm


@pytest.fixture
def dm_bridge(monkeypatch):
    import bridges.common.device.connection as connection
    import bridges.instagram.engagement.runtime.dm.bridge as runtime
    import bridges.instagram.engagement.runtime.dm.commands as bridge
    from taktik.core.social_media.instagram.workflows.core import runtime_setup
    from taktik.core.social_media.instagram.workflows.dm_inbox import agent_handler

    monkeypatch.setattr(connection, "ConnectionService", lambda device_id: SimpleNamespace())
    monkeypatch.setattr(runtime, "KeyboardService", lambda device_id: object())
    monkeypatch.setattr(runtime_setup, "prepare_instagram_selectors", lambda **kwargs: None)
    monkeypatch.setattr(bridge, "DMBridge", _dm_class())
    for name, value in (("account_id_from_inbox_header", 1), ("resolve_account_id", 1),
                        ("record_conversations", None), ("record_reply", None), ("account_id_for_send", 1),
                        ("ensure_dm_inbox", True), ("return_to_inbox", None)):
        monkeypatch.setattr(agent_handler, name, lambda *args, _value=value, **kwargs: _value)
    monkeypatch.setattr(agent_handler.time, "sleep", lambda seconds: None)
    return bridge


@pytest.mark.parametrize("contract, chosen", [
    pytest.param(INSTAGRAM_DM_READ, {"command": "read"}, id="read"),
    pytest.param(INSTAGRAM_DM_READ, {"command": "read_requests"}, id="read_requests"),
    pytest.param(INSTAGRAM_DM_SEND, {"command": "send"}, id="send"),
])
def test_the_dm_bridge_follows_its_contracts(dm_bridge, printed, contract, chosen):
    data = app_file(contract, **chosen)
    log: set = set()

    assert dm_bridge.DMCommand(Recording(data, log)).run() == 0

    assert_reads(contract, data, log)
    lines = printed()
    check_lines(contract, lines)
    expected = {event.type for event in contract.events}
    if chosen["command"] == "read_requests":
        expected -= {"account_detected"}
    assert {line["type"] for line in lines} == expected
    assert lines[-1]["type"] == "result" and lines[-1]["success"] is True


def test_a_reply_without_its_text_is_refused_in_its_last_line(dm_bridge, printed):
    data = app_file(INSTAGRAM_DM_SEND, command="send")
    data["message"] = ""

    with pytest.raises(SystemExit):
        dm_bridge.DMCommand(data).run()

    lines = printed()
    check_lines(INSTAGRAM_DM_SEND, lines)
    assert [line["type"] for line in lines] == ["result"]
    assert lines[0]["success"] is False and "traceback" not in lines[0]
