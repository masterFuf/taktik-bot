"""Probes a declared workflow contract against the code it describes (shared by the contract tests)."""

from __future__ import annotations

import importlib
import inspect
from typing import Any, Dict, Iterable, Mapping, Set, Tuple

from taktik.core.app.contract.schema import Field, ListOf, OneOf, Shape, WorkflowContract, has_default, nested_fields

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

    def items(self):
        # Iterating the payload reads every key of it (the filter criteria merge does).
        for key in list(super().keys()):
            self._note(key)
        return super().items()


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
    if spec == "json":
        return {"probe": variant}
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
    return _unit(item, (not out) if item.negate else out)


def _unit(item: Field, value: Any) -> Any:
    if item.unit == "percent":
        return float(value) / 100.0
    if item.unit == "in_list":
        return [value]
    return value


def matches(item: Field, actual: Any, wanted: Any) -> bool:
    """`merged`: the value was merged into what the reader keeps, next to other keys."""
    if item.unit == "merged":
        return isinstance(actual, Mapping) and all(actual.get(k) == v for k, v in wanted.items())
    return actual == wanted


def by_iteration(item: Field) -> bool:
    """A filter criterion reaches its reader through the merge of every flat key, not by name."""
    return bool(item.attr) and (item.attr == "filters" or item.attr.startswith("filters."))


def expected_default(item: Field) -> Any:
    default = item.default if has_default(item) else None
    if isinstance(default, tuple):
        default = list(default)
    if default is None:
        return None
    return _unit(item, (not default) if item.negate else default)


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
    result = resolve(item.reader)(payload, **item.reader_kwargs) if item.reader else read(contract, payload)
    return walk(result, item.attr) if item.attr else result


def walk(result: Any, attr: str) -> Any:
    """`attr` of the reader's result: an attribute, an index, or a dotted path into what it builds.

    A key missing from a built dict or list is None (the reader left it unset); a missing
    attribute or tuple index fails.
    """
    for part in attr.split("."):
        if isinstance(result, tuple):
            result = result[int(part)]
        elif isinstance(result, list):
            result = result[int(part)] if int(part) < len(result) else None
        elif isinstance(result, Mapping):
            result = result.get(part)
        else:
            result = getattr(result, part)
        if result is None:
            return None
    return result


def launch(contract: WorkflowContract, payload: Dict[str, Any], **kwargs: Any) -> Any:
    launcher = resolve(contract.launcher)
    if "device_id" in inspect.signature(launcher).parameters:
        kwargs.setdefault("device_id", DEVICE)
    return launcher(payload, **kwargs)


def names(fields: Iterable[Field]) -> Set[str]:
    return {name for item in fields for name in item.names}


# ------------------------------------------------------------------------------------ nested settings


def nest(path: Tuple[str, ...], value: Any) -> Dict[str, Any]:
    """`{"a": {"b": value}}` for the path `("a", "b")`."""
    out: Any = value
    for key in reversed(path):
        out = {key: out}
    return out


def merge(*parts: Dict[str, Any]) -> Dict[str, Any]:
    """The parts, nested objects merged key by key; a later value wins."""
    out: Dict[str, Any] = {}
    for part in parts:
        for key, value in part.items():
            if isinstance(value, dict) and isinstance(out.get(key), dict):
                out[key] = merge(out[key], value)
            else:
                out[key] = value
    return out


def conditions(when: Dict[str, Any]) -> Dict[str, Any]:
    """The payload a `when` stands for: dotted paths spelled out."""
    return merge(*(nest(tuple(key.split(".")), value) for key, value in when.items()))


def lookup(payload: Dict[str, Any], path: Tuple[str, ...]) -> Tuple[bool, Any]:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return False, None
        current = current[key]
    return True, current


def held_leaves(contract: WorkflowContract):
    """(path, field, when) of every setting held value by value: scalars nobody hands on (`via`)."""
    for path, item, when, via in nested_fields(contract.settings):
        if via is None and not isinstance(item.type, Shape):
            yield path, item, when


def skeleton(fields) -> Dict[str, Any]:
    """Every nested setting present, its held keys probed: the reader then reads each of them."""
    out: Dict[str, Any] = {}
    for item in fields:
        if item.via is None and isinstance(item.type, Shape):
            inner = {sub.key: probe(sub) for sub in item.type.fields
                     if sub.via is None and not isinstance(sub.type, Shape)}
            out[item.key] = merge(inner, skeleton(item.type.fields))
    return out


def reading_variants(contract: WorkflowContract):
    """The payloads under which, together, the reader reads every key it reads at all."""
    base = skeleton(contract.settings)
    whens = [when for _, _, when, _ in nested_fields(contract.settings) if when]
    if contract.selector:
        selector = contract.setting(contract.selector)
        whens += [{contract.selector: value} for value in getattr(selector.type, "values", ())]
    variants = [base] + [merge(base, conditions(when)) for when in whens]
    unique = []
    for variant in variants:
        if variant not in unique:
            unique.append(variant)
    return unique


def declared_reads(fields, prefix: Tuple[str, ...] = ()) -> Tuple[set, set]:
    """Every declared path (aliases included), and the paths handed on whole (`via`)."""
    paths, owned = set(), set()
    for path, item, _, via in nested_fields(fields, prefix):
        parent = path[:-1]
        for name in item.names:
            paths.add((*parent, name))
            if item.via:
                owned.add((*parent, name))
    return paths, owned


def under(path: Tuple[str, ...], owned: set) -> bool:
    """`path` lies strictly below a key handed on whole."""
    return any(path[:len(prefix)] == prefix and len(path) > len(prefix) for prefix in owned)
