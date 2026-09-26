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

from contract_probe import DEVICE, Recording, leaves, merge, probe, satisfied
from taktik.core.app.contract.instagram_scraping import INSTAGRAM_SCRAPING, SCRAPING_TYPES
from taktik.core.app.contract.schema import HOST, WorkflowContract, has_default
from test_workflow_contract_bridges import check_lines, declared_paths, file_paths


def _value(item) -> Any:
    return item.default if has_default(item) and not isinstance(item.default, tuple) else probe(item)


def app_file(contract: WorkflowContract, **chosen: Any) -> Dict[str, Any]:
    """The file the app writes for these choices: every setting read under them, at its wire key.

    `chosen` fixes the settings the others depend on (`type`, `deepQualify`, `ai.enabled`); a host
    field of a nested setting (the AI key) is in the file, the main process fills it."""
    data: Dict[str, Any] = {}
    for key, value in chosen.items():
        data = merge(data, {key: value})
    for prefix, item in leaves(contract):
        if prefix and prefix[0] not in data:
            continue
        if (item.by == HOST and not prefix) or not item.app or not satisfied(item, data):
            continue
        holder = data
        for key in prefix:
            holder = holder[key]
        holder.setdefault(item.key, _value(item))
    for item in contract.bridge_fields:
        data[item.key] = DEVICE if item.key == "deviceId" else "com.instagram.android"
    return data


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
            return {"success": True, "total_scraped": 1, "completion_reason": "limit_reached"}

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
