"""Probes a declared workflow contract against the code it describes (shared by the contract tests)."""

from __future__ import annotations

import importlib
import inspect
from typing import Any, Dict, Iterable, List, Mapping, Set, Tuple

from taktik.core.app.contract.schema import Field, ListOf, MapOf, OneOf, Shape, WorkflowContract, has_default

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
    if isinstance(spec, MapOf) and spec.value == ListOf("string"):
        return {f"slug{variant}": [f"alpha{variant}"]}
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
    result = read(contract, payload)
    # A reader that returns a dict leaves out what the payload does not set.
    return result.get(item.attr) if isinstance(result, Mapping) else getattr(result, item.attr)


def launch(contract: WorkflowContract, payload: Dict[str, Any], **kwargs: Any) -> Any:
    launcher = resolve(contract.launcher)
    parameters = inspect.signature(launcher).parameters
    if "device_id" in parameters:
        kwargs.setdefault("device_id", DEVICE)
    # A refusal comes before the phone: what the host injects (device manager, runtime) is None,
    # and a launcher that needs it to refuse fails the test.
    for name, parameter in parameters.items():
        if parameter.kind is parameter.KEYWORD_ONLY and parameter.default is parameter.empty:
            kwargs.setdefault(name, None)
    return launcher(payload, **kwargs)


# ------------------------------------------------------------------ nested and conditional settings


def leaves(contract: WorkflowContract) -> List[Tuple[Tuple[str, ...], Field]]:
    """Each setting with the path of the object holding it: a group (`ai`) stands for its fields."""
    out: List[Tuple[Tuple[str, ...], Field]] = []
    for item in contract.settings:
        if isinstance(item.type, Shape) and not item.attr and not item.reader:
            out += [((item.key,), sub) for sub in item.type.fields]
        else:
            out.append(((), item))
    return out


def merge(base: Dict[str, Any], extra: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in extra.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = merge(dict(out[key]), value)
        else:
            out[key] = value
    return out


def at(path: Tuple[str, ...], value: Any) -> Dict[str, Any]:
    """`{"a": {"b": value}}` for the path `("a", "b")`."""
    for key in reversed(path):
        value = {key: value}
    return value


def conditions(item: Field) -> Dict[str, Any]:
    """A payload fragment under which `item` is read (the first value its `when` accepts)."""
    out: Dict[str, Any] = {}
    for dotted, wanted in item.when.items():
        value = wanted[0] if isinstance(wanted, tuple) else wanted
        out = merge(out, at(tuple(dotted.split(".")), value))
    return out


def given(payload: Mapping[str, Any], path: Tuple[str, ...]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            return None
        value = value[key]
    return value


def satisfied(item: Field, payload: Mapping[str, Any]) -> bool:
    """The payload, as given, holds what `item.when` asks: the reader reads `item`."""
    for dotted, wanted in item.when.items():
        value = given(payload, tuple(dotted.split(".")))
        if not (value in wanted if isinstance(wanted, tuple) else value == wanted):
            return False
    return True


def payload_of(contract: WorkflowContract, prefix: Tuple[str, ...], item: Field,
               values: Mapping[str, Any]) -> Dict[str, Any]:
    """A runnable payload under which `item` is read, with `values` (name -> value) at its place."""
    fragment = conditions(item)
    for name, value in values.items():
        fragment = merge(fragment, at((*prefix, name), value))
    return payload_for(contract, fragment)


def declared_setting_paths(contract: WorkflowContract) -> Set[Tuple[str, ...]]:
    """Every path a reader may read: each name of each setting, and of the fields of a group."""
    paths: Set[Tuple[str, ...]] = set()
    for item in contract.settings:
        for name in item.names:
            paths.add((name,))
            if isinstance(item.type, Shape):
                paths |= {(name, sub_name) for sub in item.type.fields for sub_name in sub.names}
    return paths


def names(fields: Iterable[Field]) -> Set[str]:
    return {name for item in fields for name in item.names}
