"""The Instagram automation bridge reads the file the contract describes (`instagram_automation.py`).

The whole `DesktopBridge` runs, from its config file to the end of the run, on the app's file for
each workflow of the family; only what touches the phone, the network or the base is replaced
(the device connection, the start of Instagram, the IP rotation, the automation itself). The AI
hooks and the AI service are the real ones. What is held to the declaration:
- every key of the file is read by one run of the family or another, and every key read is
  declared (below a key handed on whole, `via`, the function it is handed to reads what it wants);
- the closed sets of the declaration are the reader's own.

The reader itself is held key by key by `test_workflow_contract_readers.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from contract_probe import DEVICE, Recording, declared_reads, under
from taktik.core.app.contract.instagram_automation import INSTAGRAM_AUTOMATION, WORKFLOW_TYPES
from taktik.core.app.contract.schema import HOST, Field, ListOf, MapOf, OneOf, Shape, has_default

CORE = Path(__file__).resolve().parents[4]
_HOOKED = (
    ("taktik.core.social_media.instagram.actions.business.workflows.post_url.workflow", "PostUrlBusiness",
     "in_thread_reply_writer"),
    ("taktik.core.social_media.instagram.actions.business.actions.comment.action", "CommentAction",
     "comment_on_post"),
    ("taktik.core.social_media.instagram.actions.core.base_business.interaction_engine", "InteractionEngineMixin",
     "_perform_interactions_on_profile"),
    ("taktik.core.social_media.instagram.actions.business.actions.like.orchestration", "LikeOrchestration",
     "like_current_post"),
)


# ------------------------------------------------------------------------------------ the file


def _value(item: Field) -> Any:
    """What the app writes for `item`: its default, or a value the run acts on."""
    if has_default(item) and not isinstance(item.default, tuple):
        return item.default
    spec = item.type
    if isinstance(spec, OneOf):
        return spec.values[-1]
    if isinstance(spec, ListOf):
        return ["alpha", "beta"]
    if isinstance(spec, MapOf):
        return {"fitness": ["yoga"]}
    return {"int": 7, "number": 2.5, "bool": True, "string": "probe", "json": {}}[spec]


def _fill(fields) -> Dict[str, Any]:
    return {item.key: _fill(item.type.fields) if isinstance(item.type, Shape) else _value(item)
            for item in fields if item.app}


def bridge_file(workflow_type: str) -> Dict[str, Any]:
    """The file the app writes for one workflow: every app key, the host's keys, the bridge's."""
    data = _fill((*INSTAGRAM_AUTOMATION.settings, *INSTAGRAM_AUTOMATION.bridge_fields))
    data.update(deviceId=DEVICE, workflowType=workflow_type, target="alpha,beta")
    data["networkReset"] = {"enabled": True, "method": "data"}
    data["mediaCaptureEnabled"] = False
    # Decision mode on, so the plans' capabilities are read; the key long enough to build the service.
    data["ai"].update(enabled=True, openrouterApiKey="sk-probe-key-long-enough")
    data["ai"]["decision"]["mode"] = "decide"
    return data


def file_paths(data: Dict[str, Any], prefix=()) -> set:
    out = set()
    for key, value in data.items():
        out.add((*prefix, key))
        if isinstance(value, dict):
            out |= file_paths(value, (*prefix, key))
    return out


# ------------------------------------------------------------------------------------ the run


class _Automation:
    def __init__(self, device_manager):
        self.device_manager = device_manager

    def run_workflow(self):
        return None

    def final_stats(self):
        return {"likes": 1, "follows": 0, "comments": 0, "interactions": 1, "unfollows": 0}


class _DecisionClient:
    def __init__(self, **_):
        pass

    def request_plan(self, facts):
        return {}

    def close(self, *_, **__):
        return None


@pytest.fixture
def desktop_bridge(monkeypatch):
    """`DesktopBridge` with the phone, the network, the base and the automation replaced."""
    import importlib

    import bridges.common.device.network as network
    import bridges.instagram.automation.runtime.bridge as bridge
    import taktik.core.social_media.instagram.workflows.core.automation as automation
    import taktik.core.social_media.instagram.workflows.core.runtime_setup as runtime_setup
    from bridges.common.runtime.ipc import IPC
    from bridges.instagram.automation.runtime.session import InstagramDesktopRuntime

    printed: List[Dict[str, Any]] = []
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **kwargs: printed.append({"type": msg_type, **kwargs}))
    monkeypatch.setattr(network, "_emit_network_baseline", lambda device_id: None)
    monkeypatch.setattr(
        network, "perform_network_reset",
        lambda *a, **k: SimpleNamespace(should_block_run=False, describe=lambda: "rotated"),
    )

    def connect(runtime):
        runtime.device_manager = SimpleNamespace(device=object())
        return True

    monkeypatch.setattr(InstagramDesktopRuntime, "setup_database", lambda runtime: True)
    monkeypatch.setattr(InstagramDesktopRuntime, "connect_device", connect)
    monkeypatch.setattr(InstagramDesktopRuntime, "launch_instagram", lambda runtime: True)
    monkeypatch.setattr(InstagramDesktopRuntime, "stop_app", lambda runtime: None)
    monkeypatch.setattr(bridge, "register_desktop_shutdown_handlers", lambda handler, ipc: None)
    monkeypatch.setattr(bridge, "DesktopProfileDecisionClient", _DecisionClient)
    monkeypatch.setattr(automation, "InstagramAutomation", _Automation)
    monkeypatch.setattr(runtime_setup, "prepare_instagram_automation_runtime", lambda **kwargs: None)
    # The AI hooks patch these classes for the run: put them back afterwards.
    for module, owner, name in _HOOKED:
        cls = getattr(importlib.import_module(module), owner)
        monkeypatch.setattr(cls, name, getattr(cls, name, None), raising=False)
    return bridge.DesktopBridge, printed


# ------------------------------------------------------------------------------------ tests


def test_the_desktop_bridge_reads_the_declared_file(desktop_bridge):
    DesktopBridge, printed = desktop_bridge
    declared, owned = declared_reads((*INSTAGRAM_AUTOMATION.settings, *INSTAGRAM_AUTOMATION.bridge_fields))
    unread = None
    for workflow_type in WORKFLOW_TYPES:
        data = bridge_file(workflow_type)
        log: set = set()

        assert DesktopBridge(Recording(data, log)).run() == 0, (workflow_type, printed[-3:])

        undeclared = {path for path in log if path not in declared and not under(path, owned)}
        assert not undeclared, f"{workflow_type}: keys read and not declared: {sorted(undeclared)}"
        left = {path for path in file_paths(data) - log if not under(path, owned)}
        unread = left if unread is None else unread & left
    assert not unread, f"keys of the file no workflow reads: {sorted(unread)}"
    assert {line["type"] for line in printed} >= {"status", "session_config", "stats"}


def test_the_family_is_the_readers_and_the_manifests():
    from taktik.core.social_media.instagram.workflows.core.agent_handler import INSTAGRAM_AUTOMATION_WORKFLOW_TYPES
    from taktik.core.social_media.instagram.workflows.core.config_builder import SUPPORTED_WORKFLOW_TYPES

    manifest = json.loads((CORE / "workflows.manifest.json").read_text(encoding="utf-8-sig"))
    automation = manifest["instagram"]["automation"]

    assert set(WORKFLOW_TYPES) == set(SUPPORTED_WORKFLOW_TYPES)
    assert set(WORKFLOW_TYPES) == set(INSTAGRAM_AUTOMATION_WORKFLOW_TYPES) - {"notifications"}
    assert set(WORKFLOW_TYPES) == set(automation) - {"notifications"}
    assert INSTAGRAM_AUTOMATION.setting("workflowType").type.values == WORKFLOW_TYPES
    bridges = json.loads((CORE / "bridges" / "bridges.manifest.json").read_text(encoding="utf-8-sig"))
    assert INSTAGRAM_AUTOMATION.bridge in bridges["instagram"]


def test_the_reader_refuses_a_workflow_outside_the_declaration():
    from taktik.core.social_media.instagram.workflows.core.config_builder import build_instagram_automation_config

    for workflow_type in ("notifications", "cold_dm"):
        with pytest.raises(ValueError):
            build_instagram_automation_config({"workflowType": workflow_type, "target": "alpha"})


def test_the_closed_sets_are_the_bots():
    from taktik.core.shared.behavior.policy import PROFILE_IDS
    from taktik.core.social_media.instagram.actions.business.workflows.common.distribution import _VALID_MODES
    from taktik.core.social_media.instagram.actions.business.workflows.unfollow.candidates import MODES

    ai = INSTAGRAM_AUTOMATION.setting("ai").type
    assert set(INSTAGRAM_AUTOMATION.setting("behaviorPolicy").type.fields[0].type.values) == set(PROFILE_IDS)
    assert set(INSTAGRAM_AUTOMATION.setting("distribution").type.values) == set(_VALID_MODES)
    unfollow = {item.key: item for item in INSTAGRAM_AUTOMATION.setting("unfollow").type.fields}
    assert unfollow["unfollowMode"].type.values == MODES
    assert {item.key for item in ai.fields if item.by == HOST} >= {"openrouterApiKey", "accountProfile"}
