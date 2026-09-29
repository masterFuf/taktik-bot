"""What the Instagram automation contract tests share: the app's file, the lines a run prints."""

from __future__ import annotations

import importlib
import json
from typing import Any, Dict, List

from contract_probe import DEVICE
from taktik.core.contract.instagram_automation import INSTAGRAM_AUTOMATION
from taktik.core.contract.schema import Field, ListOf, MapOf, OneOf, Shape, has_default

#: Classes the AI hooks patch for a run; a test puts them back.
HOOKED = (
    ("taktik.core.social_media.instagram.actions.business.workflows.post_url.workflow", "PostUrlBusiness",
     "in_thread_reply_writer"),
    ("taktik.core.social_media.instagram.actions.business.actions.comment.action", "CommentAction",
     "comment_on_post"),
    ("taktik.core.social_media.instagram.actions.core.base_business.interaction_engine", "InteractionEngineMixin",
     "_perform_interactions_on_profile"),
    ("taktik.core.social_media.instagram.actions.business.actions.like.orchestration", "LikeOrchestration",
     "like_current_post"),
)


def use_the_bridge_ipc(monkeypatch) -> None:
    """The Instagram bridge's own IPC behind `IPCEmitter` and the step telemetry, whatever ran before.

    Both are process-wide and set only by the first import of `bridges.instagram.runtime.ipc`: a test
    that relies on that import finds whatever an earlier test left there."""
    import sys

    import bridges.instagram.runtime.ipc as instagram_ipc
    import taktik.core.shared.telemetry.sink as telemetry
    from taktik.core.social_media.instagram.actions.core.ipc import emitter

    monkeypatch.setattr(emitter, "_bridge_adapter", sys.modules[instagram_ipc.__name__])
    monkeypatch.setattr(telemetry, "_sink", telemetry._sink)
    instagram_ipc._register_telemetry_sink()


def protect_hooks(monkeypatch) -> None:
    for module, owner, name in HOOKED:
        cls = getattr(importlib.import_module(module), owner)
        monkeypatch.setattr(cls, name, getattr(cls, name, None), raising=False)


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


# ------------------------------------------------------------------------------------ the lines


def capture_lines(monkeypatch) -> List[Dict[str, Any]]:
    """Every line sent through the IPC channel; lines printed directly are read from stdout."""
    from bridges.common.runtime.ipc import IPC

    sent: List[Dict[str, Any]] = []
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **kwargs: sent.append({"type": msg_type, **kwargs}))
    return sent


def printed_lines(text: str) -> List[Dict[str, Any]]:
    """The JSON lines of a captured stdout."""
    out = []
    for raw in text.splitlines():
        raw = raw.strip()
        if raw.startswith("{") and raw.endswith("}"):
            try:
                line = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(line, dict) and "type" in line:
                out.append(line)
    return out


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
        return spec.allows(value)
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
        elif data[key] is None:
            if not item.nullable:
                problems.append(f"{key} is null")
        elif not _is(item.type, data[key]):
            problems.append(f"{key}={data[key]!r} is not {item.type!r}")
    return problems


def line_problems(lines: List[Dict[str, Any]]) -> List[str]:
    """What in `lines` the contract does not declare: a `type`, a field, a type of value."""
    declared = {event.type: event for event in INSTAGRAM_AUTOMATION.events}
    out = []
    for line in lines:
        json.dumps(line)
        event = declared.get(line["type"])
        if event is None:
            out.append(f"undeclared line {line['type']}: {line}")
            continue
        out += [f"{line['type']}: {problem}" for problem in problems_of(event.fields, line)]
    return out
