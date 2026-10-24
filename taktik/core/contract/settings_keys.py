"""A key the declaration of a workflow does not have: named, with where the declaration has it.

The app checks the settings of its tools against a strict schema built from the generated contract
(`workflowSettingsSchema`, app side). The CLI checks its `--json` and its `--param` against the same
declaration, read here: the settings and their aliases (the names a CLI run or an Agent plan may
send), the nested settings, the ones another value of the selector reads (`when`), the bridge fields
and the keys the host fills itself. What a setting of type `json` holds is its reader's, read whole;
so are the items of a list or of a map that are not nested settings.

In Symfony terms: the `allow_extra_fields: false` of a form type, with the form type written once,
in `taktik/core/contract/`.

Phone session of 2026-10-24: `--json '{"maxProfiles": 2, "durationMinutes": 10}'` on the feed was
accepted without a word, and the run took its defaults; the declaration reads them under `limits`
and `session`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, List, Mapping, Optional, Sequence, Tuple

from .registry import contracts_by_id, selector_value
from .schema import Field, ListOf, MapOf, Shape, WorkflowContract


@dataclass(frozen=True)
class UndeclaredSetting:
    """A key sent where the declaration has no setting of that name.

    path         where it was sent, dotted (`maxProfiles`, `limits.max_profile`)
    declared_at  where the declaration has a setting of that name, in any spelling the reader
                 accepts or with another case or underscores (`limits.maxProfiles`)
    read_by      the declaration has the key there, but reads it only under another value of its
                 selector (`workflowType feed`)
    """

    path: str
    declared_at: Tuple[str, ...] = ()
    read_by: Tuple[str, ...] = ()

    def sentence(self, workflow_id: str) -> str:
        said = f"`{self.path}` is not a setting of {workflow_id}"
        if self.read_by:
            said += f" (read only by {', '.join(self.read_by)})"
        if self.declared_at:
            said += "; expected as " + " or ".join(f"`{path}`" for path in self.declared_at)
        return said


def _spelling(name: str) -> str:
    """A name with its case and underscores dropped: `max_profiles` and `maxProfiles` meet here."""
    return name.replace("_", "").lower()


def _admitted(item: Field, contract: WorkflowContract, value: Optional[str]) -> bool:
    """The workflow reads `item`: no condition on the selector, or one its value meets. A condition on
    another setting is the reader's to judge."""
    selector = contract.selector
    if value is None or selector is None or selector not in item.when:
        return True
    wanted = item.when[selector]
    return value in wanted if isinstance(wanted, tuple) else value == wanted


def _readers(item: Field, contract: WorkflowContract) -> Tuple[str, ...]:
    """The values of the selector under which the workflow reads `item` (`workflowType feed`)."""
    selector = contract.selector
    if selector is None or selector not in item.when:
        return ()
    wanted = item.when[selector]
    return tuple(f"{selector} {one}" for one in (wanted if isinstance(wanted, tuple) else (wanted,)))


def _nested_shape(spec: Any) -> Optional[Shape]:
    """The nested setting a value holds: a `Shape`, or the items of a list or a map of them."""
    if isinstance(spec, (ListOf, MapOf)):
        spec = spec.item if isinstance(spec, ListOf) else spec.value
    return spec if isinstance(spec, Shape) else None


def _paths(fields: Sequence[Field], contract: WorkflowContract, value: Optional[str],
           prefix: str = "") -> Iterator[Tuple[str, Field]]:
    """Every setting the workflow reads, nested ones included, with its dotted path."""
    for item in fields:
        if not _admitted(item, contract, value):
            continue
        path = f"{prefix}{item.key}"
        yield path, item
        shape = _nested_shape(item.type)
        if shape is not None:
            yield from _paths(shape.fields, contract, value, f"{path}.")


def undeclared_settings(workflow_id: str, payload: Mapping[str, Any],
                        host_keys: Sequence[str] = ()) -> List[UndeclaredSetting]:
    """The keys of `payload` the declaration of `workflow_id` does not read, in the order they were
    sent; [] when it reads them all. `host_keys`: what the host itself puts in the payload (the
    serial), accepted at the root. A workflow no declaration serves is a `KeyError`."""
    contract = contracts_by_id()[workflow_id]
    value = selector_value(contract, workflow_id)
    every_path = list(_paths(contract.settings, contract, value))
    root = (*contract.settings, *contract.bridge_fields)
    found: List[UndeclaredSetting] = []
    _check(payload, root, "", contract, value, every_path, tuple(host_keys), found)
    return found


def _check(node: Mapping[str, Any], fields: Sequence[Field], prefix: str, contract: WorkflowContract,
           value: Optional[str], every_path: List[Tuple[str, Field]], host_keys: Tuple[str, ...],
           found: List[UndeclaredSetting]) -> None:
    by_name = {name: item for item in fields for name in item.names}
    for key, sent in node.items():
        item = by_name.get(key)
        if item is None and key in host_keys:
            continue
        if item is None or not _admitted(item, contract, value):
            spelling = _spelling(key)
            found.append(UndeclaredSetting(
                path=f"{prefix}{key}",
                declared_at=tuple(path for path, other in every_path
                                  if any(_spelling(name) == spelling for name in other.names)),
                read_by=_readers(item, contract) if item is not None else (),
            ))
            continue
        shape = _nested_shape(item.type)
        if shape is None:
            continue
        path = f"{prefix}{item.key}"
        if isinstance(item.type, Shape) and isinstance(sent, Mapping):
            _check(sent, shape.fields, f"{path}.", contract, value, every_path, (), found)
        elif isinstance(item.type, ListOf) and isinstance(sent, list):
            for index, one in enumerate(sent):
                if isinstance(one, Mapping):
                    _check(one, shape.fields, f"{path}[{index}].", contract, value, every_path, (), found)
        elif isinstance(item.type, MapOf) and isinstance(sent, Mapping):
            for name, one in sent.items():
                if isinstance(one, Mapping):
                    _check(one, shape.fields, f"{path}.{name}.", contract, value, every_path, (), found)


__all__ = ["UndeclaredSetting", "undeclared_settings"]
