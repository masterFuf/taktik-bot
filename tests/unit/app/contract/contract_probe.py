"""Probes a declared workflow contract against the code it describes (shared by the contract tests)."""

from __future__ import annotations

import importlib
import inspect
from typing import Any, Dict, Iterable, Set, Tuple

from taktik.core.app.contract.schema import Field, ListOf, OneOf, WorkflowContract, has_default

DEVICE = "emulator-5554"


def resolve(dotted: str):
    module, name = dotted.split(":")
    return getattr(importlib.import_module(module), name)


class Recording(dict):
    """A payload that notes every key read from it; nested objects are recorded the same way.

    A key the code under test wrote itself is not a read of the payload.
    """

    def __init__(self, data: Dict[str, Any], log: Set[Tuple[str, ...]], prefix: Tuple[str, ...] = ()):
        super().__init__()
        self._log = log
        self._prefix = prefix
        self._written: Set[str] = set()
        for key, value in data.items():
            super().__setitem__(key, Recording(value, log, (*prefix, key)) if isinstance(value, dict) else value)

    def _note(self, key: Any) -> None:
        if isinstance(key, str) and key not in self._written:
            self._log.add((*self._prefix, key))

    def get(self, key, default=None):
        self._note(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self._note(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        self._note(key)
        return super().__contains__(key)

    def __setitem__(self, key, value):
        self._written.add(key)
        super().__setitem__(key, value)


def probe(item: Field, variant: int = 0) -> Any:
    """A value for `item` that differs from its default, and from the probe of another variant."""
    default = item.default if has_default(item) else None
    spec = item.type
    if spec == "int":
        return int(default or 0) + 7 + variant
    if spec == "number":
        return float(default or 0) + 2.5 + variant
    if spec == "bool":
        base = default if isinstance(default, bool) else False
        return (not base) if variant == 0 else base
    if spec == "string":
        return f"probe{variant}"
    if isinstance(spec, OneOf):
        others = [value for value in spec.values if value != default]
        return others[variant % len(others)]
    if isinstance(spec, ListOf) and spec.item == "string":
        return [f"alpha{variant}", f"beta{variant}"]
    raise AssertionError(f"no probe for {item.key}: {spec!r}")


def expected(item: Field, value: Any) -> Any:
    """What the reader's result holds for `value` sent under `item`."""
    spec = item.type
    if spec == "int":
        out = int(value)
    elif spec == "number":
        out = float(value)
    elif spec == "bool":
        out = bool(value)
    elif isinstance(spec, ListOf):
        out = list(value)
    else:
        out = value
    return (not out) if item.negate else out


def expected_default(item: Field) -> Any:
    default = item.default if has_default(item) else None
    if isinstance(default, tuple):
        default = list(default)
    return (not default) if item.negate else default


def payload_for(contract: WorkflowContract, extra: Dict[str, Any]) -> Dict[str, Any]:
    """`extra`, completed with what the refusals of the contract require for it to run."""
    payload = dict(extra)
    for refusal in contract.refusals:
        needed = contract.setting(refusal.missing)
        if any(name in payload for name in needed.names):
            continue
        effective = {}
        for key in refusal.when:
            item = contract.setting(key)
            given = next((payload[name] for name in item.names if name in payload), None)
            effective[key] = given if given is not None else (item.default if has_default(item) else None)
        if all(effective[key] == value for key, value in refusal.when.items()):
            payload[needed.key] = probe(needed, variant=9)
    return payload


def read(contract: WorkflowContract, payload: Dict[str, Any]) -> Any:
    kwargs = {key: (DEVICE if value == "<device>" else value) for key, value in contract.reader_kwargs.items()}
    return resolve(contract.reader)(payload, **kwargs)


def value_of(contract: WorkflowContract, item: Field, payload: Dict[str, Any]) -> Any:
    if item.reader:
        return resolve(item.reader)(payload)
    return getattr(read(contract, payload), item.attr)


def launch(contract: WorkflowContract, payload: Dict[str, Any], **kwargs: Any) -> Any:
    launcher = resolve(contract.launcher)
    if "device_id" in inspect.signature(launcher).parameters:
        kwargs.setdefault("device_id", DEVICE)
    return launcher(payload, **kwargs)


def names(fields: Iterable[Field]) -> Set[str]:
    return {name for item in fields for name in item.names}
