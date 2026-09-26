"""Each declared bridge reads the file the contract describes and prints the lines it declares.

The whole bridge runs, from its config file to its stdout, on the app's file for the workflow; only
what touches the phone, the network or the base is replaced (the workflow's screen work, the
start of TikTok, the IP rotation, the rows). What is held to the declaration:
- every key of the file is read, and every key read is declared (bridge and launcher together);
- every line printed is a declared `type` with its declared fields and types;
- every declared `type` is printed by a real path of the bridge.
"""

from __future__ import annotations

import json
import random
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from contract_probe import DEVICE, Recording, probe
from taktik.core.app.contract.schema import Field, ListOf, MapOf, OneOf, Shape, WorkflowContract, has_default
from taktik.core.app.contract.tiktok import TIKTOK_DM_OUTREACH, TIKTOK_SCRAPING, TIKTOK_UNFOLLOW

_WORKFLOWS = "taktik.core.social_media.tiktok.actions.business.workflows"


# ------------------------------------------------------------------------------------ helpers


def bridge_file(contract: WorkflowContract, **overrides: Any) -> Dict[str, Any]:
    """The file the app writes: every app setting under its wire key, the bridge fields."""
    settings = {}
    for item in contract.settings:
        if not item.app or item.by != "operator":
            continue
        plain = has_default(item) and not isinstance(item.default, tuple)
        settings[item.key] = item.default if plain else probe(item)
    settings.update(overrides)
    root: Dict[str, Any] = {}
    for item in contract.bridge_fields:
        value = DEVICE if item.key in ("device_id", "deviceId") else {"enabled": True, "method": "data"}
        target = settings if item.key in contract.beside_settings or not contract.nest else root
        target[item.key] = value
    if contract.nest:
        root[contract.nest] = settings
        return root
    return {**root, **settings}


def declared_paths(contract: WorkflowContract) -> set:
    nest = (contract.nest,) if contract.nest else ()
    paths = set()

    def add(item: Field, prefix):
        for name in item.names:
            paths.add((*prefix, name))
            if isinstance(item.type, Shape):
                for sub in item.type.fields:
                    add(sub, (*prefix, name))

    for item in contract.settings:
        add(item, nest)
    for item in contract.bridge_fields:
        add(item, nest if item.key in contract.beside_settings else ())
    if contract.nest:
        paths.add(nest)
    return paths


def file_paths(data: Dict[str, Any], prefix=()) -> set:
    out = set()
    for key, value in data.items():
        out.add((*prefix, key))
        if isinstance(value, dict):
            out |= file_paths(value, (*prefix, key))
    return out


def conforms(item: Field, value: Any) -> bool:
    if value is None:
        return item.nullable
    return _is(item.type, value)


def _is(spec: Any, value: Any) -> bool:
    if spec == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if spec == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if spec == "bool":
        return isinstance(value, bool)
    if spec == "string":
        return isinstance(value, str)
    if spec == "json":
        return True
    if isinstance(spec, OneOf):
        return value in spec.values
    if isinstance(spec, ListOf):
        return isinstance(value, list) and all(_is(spec.item, v) for v in value)
    if isinstance(spec, MapOf):
        return isinstance(value, dict) and all(_is(spec.value, v) for v in value.values())
    if isinstance(spec, Shape):
        return isinstance(value, dict) and not problems_of(spec.fields, value)
    raise AssertionError(f"unknown spec {spec!r}")


def problems_of(fields, data: Dict[str, Any]) -> List[str]:
    declared = {item.key: item for item in fields}
    problems = [f"undeclared field {key}" for key in data if key not in declared and key != "type"]
    for key, item in declared.items():
        if key not in data:
            if not item.optional:
                problems.append(f"missing field {key}")
        elif not conforms(item, data[key]):
            problems.append(f"{key}={data[key]!r} is not {item.type!r}")
    return problems


def check_lines(contract: WorkflowContract, lines: List[Dict[str, Any]]) -> None:
    declared = {event.type: event for event in contract.events}
    for line in lines:
        json.dumps(line)
        assert line["type"] in declared, f"undeclared line {line}"
        assert not problems_of(declared[line["type"]].fields, line), (line, problems_of(declared[line["type"]].fields, line))


@pytest.fixture
def lines(monkeypatch):
    """Every line the bridge prints, through the real IPC helpers."""
    from bridges.common.runtime.ipc import IPC

    printed: List[Dict[str, Any]] = []
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **kwargs: printed.append({"type": msg_type, **kwargs}))
    return printed


@pytest.fixture
def no_ip_rotation(monkeypatch):
    import bridges.common.device.network as network

    monkeypatch.setattr(network, "_emit_network_baseline", lambda device_id: None)
    monkeypatch.setattr(
        network, "perform_network_reset",
        lambda *a, **k: SimpleNamespace(should_block_run=False, describe=lambda: "rotated"),
    )


def started(monkeypatch, bridge_module):
    from taktik.core.social_media.tiktok.workflows.runtime.startup import TikTokStartup

    start = TikTokStartup(device=object(), bot_username="acting")
    monkeypatch.setattr(bridge_module, "tiktok_startup_provider", lambda device_id: lambda: start)


def assert_reads(contract: WorkflowContract, data: Dict[str, Any], log: set) -> None:
    unread = file_paths(data) - log
    undeclared = log - declared_paths(contract)
    assert not unread, f"keys of the file nobody reads: {sorted(unread)}"
    assert not undeclared, f"keys read and not declared: {sorted(undeclared)}"


# ------------------------------------------------------------------------------------ unfollow


class _Unfollow:
    fail = False

    def __init__(self, device, config):
        self.config = config
        self.callbacks = {}

    def __getattr__(self, name):
        if name.startswith("set_on_") and name.endswith("_callback"):
            return lambda cb: self.callbacks.__setitem__(name[len("set_on_"):-len("_callback")], cb)
        raise AttributeError(name)

    def run(self):
        from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.models import UnfollowStats

        if self.fail:
            raise RuntimeError("the list did not open")
        self.callbacks["unfollow"]("alice", 1)
        self.callbacks["skip"]("bob", "friends")
        self.callbacks["skip"](None, "handle_unknown")
        self.callbacks["unconfirmed"]("carol", "following")
        stats = UnfollowStats(unfollowed=1, skipped_friends=1, unconfirmed=1, refusals={"friends": 1})
        self.callbacks["stats"](stats.to_dict())
        stats.stop_reason = "unfollow_unconfirmed"
        return stats


@pytest.mark.parametrize("fail", [False, True], ids=["run", "failure"])
def test_the_unfollow_bridge_follows_its_contract(monkeypatch, lines, no_ip_rotation, fail):
    import bridges.tiktok.automation.runtime.unfollow as bridge
    import taktik.core.social_media.tiktok.actions.business.workflows.unfollow.workflow as workflow

    started(monkeypatch, bridge)
    monkeypatch.setattr(_Unfollow, "fail", fail)
    monkeypatch.setattr(workflow, "UnfollowWorkflow", _Unfollow)
    data = bridge_file(TIKTOK_UNFOLLOW)
    log: set = set()

    assert bridge.TikTokUnfollowBridge(Recording(data, log)).run() == (1 if fail else 0)

    assert_reads(TIKTOK_UNFOLLOW, data, log)
    check_lines(TIKTOK_UNFOLLOW, lines)
    expected = {"status", "error"} if fail else {"status", "unfollow_event", "unfollow_stats"}
    assert {line["type"] for line in lines} == expected


# ------------------------------------------------------------------------------------- cold DM


def _outreach_class():
    from taktik.core.social_media.tiktok.actions.business.workflows.dm import outreach

    class Outreach(outreach.TikTokDMOutreachWorkflow):
        """The production workflow; only what it asks of the phone answers from a script."""

        def __init__(self, device_id, **kwargs):
            super().__init__(device_id, rng=random.Random(0), sleeper=lambda seconds: None, **kwargs)

        def connect(self):
            self.navigation = SimpleNamespace(navigate_to_home=lambda: None)
            return True

        def navigate_to_user_profile(self, username):
            return username != "bob"

        def open_conversation_from_profile(self):
            return outreach.NO_MESSAGE_ENTRY if self._current == "carol" else outreach.CONVERSATION_OPENED

        def _process_recipient(self, recipient, *args, **kwargs):
            self._current = recipient
            return super()._process_recipient(recipient, *args, **kwargs)

        def send_dm(self, message):
            return {"dave": "privacy_blocked", "erin": False, "frank": outreach.ACTION_BLOCKED}.get(self._current, True)

    return Outreach


def test_the_cold_dm_bridge_follows_its_contract(monkeypatch, lines, no_ip_rotation):
    import bridges.tiktok.engagement.runtime.dm_outreach as bridge
    import taktik.core.database.tiktok_dm as sent_dms
    from taktik.core.social_media.tiktok.actions.business.workflows.dm import agent_handler

    monkeypatch.setattr(agent_handler, "_default_outreach_factory", _outreach_class)
    monkeypatch.setattr(sent_dms, "cold_dm_already_sent", lambda *a, **k: False)
    monkeypatch.setattr(sent_dms, "record_cold_dm", lambda *a, **k: None)
    recipients = ["alice", "bob", "carol", "dave", "erin", "frank"]
    data = bridge_file(TIKTOK_DM_OUTREACH, recipients=recipients, maxDms=len(recipients), messages=["Hello"])
    log: set = set()

    assert bridge.TikTokDMOutreachBridge(Recording(data, log)).run() == 0
    assert_reads(TIKTOK_DM_OUTREACH, data, log)

    from bridges.tiktok.runtime.ipc import _ipc, send_error

    # The AI transport's own report of a paid call, and the bridge's error helper.
    _ipc.ai_spend(0.0012, model="qwen", label="alice", kind="dm")
    send_error("DM Outreach error: the phone went away")
    check_lines(TIKTOK_DM_OUTREACH, lines)
    assert {line["type"] for line in lines} == {event.type for event in TIKTOK_DM_OUTREACH.events}


# ------------------------------------------------------------------------------------ scraping


class _Scraping:
    def __init__(self, device, navigation, config):
        from taktik.core.social_media.tiktok.actions.business.workflows.scraping.models import ScrapingStats

        self.config = config
        self.callbacks = {}
        self.completion_reason = None
        self.stats = ScrapingStats()

    def __getattr__(self, name):
        if name.startswith("set_on_") and name.endswith("_callback"):
            return lambda cb: self.callbacks.__setitem__(name[len("set_on_"):-len("_callback")], cb)
        raise AttributeError(name)

    def run(self):
        profile = {"username": "alice", "followers_count": 12, "following_count": 3}
        self.callbacks["status"]("running", "Reading @target's followers")
        self.callbacks["progress"](1, self.config.max_profiles, "alice")
        self.callbacks["profile"](profile)
        self.callbacks["save_profile"](profile)
        self.callbacks["error"]("One profile did not open")
        self.completion_reason = "completed"
        return [profile]


def test_the_scraping_bridge_follows_its_contract(monkeypatch, lines):
    import bridges.tiktok.scraping.runtime.workflow as bridge
    import taktik.core.database.tiktok_scraping as rows
    from taktik.core.social_media.tiktok.actions.business.workflows.scraping import agent_handler

    started(monkeypatch, bridge)
    monkeypatch.setattr(agent_handler, "_default_workflow_factory", lambda: _Scraping)
    monkeypatch.setattr(agent_handler, "_default_navigation_factory", lambda: (lambda device: object()))
    monkeypatch.setattr(rows, "open_scraping_session", lambda *a, **k: 7)
    monkeypatch.setattr(rows, "save_scraped_profile", lambda *a, **k: None)
    monkeypatch.setattr(rows, "close_scraping_session", lambda *a, **k: None)
    data = bridge_file(TIKTOK_SCRAPING)
    log: set = set()

    assert bridge.TikTokScrapingBridge(Recording(data, log)).run() == 0

    assert_reads(TIKTOK_SCRAPING, data, log)
    check_lines(TIKTOK_SCRAPING, lines)
    assert {line["type"] for line in lines} == {event.type for event in TIKTOK_SCRAPING.events}
