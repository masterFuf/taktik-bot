#!/usr/bin/env python3
"""Render the bot/app contract (`taktik/core/app/contract/`) for the desktop app.

The app's types for the declared workflows are generated from the declaration, never written by
hand: the settings each workflow reads, the file its bridge reads, the lines its bridge prints.
The output is deterministic (declaration order, no date), so the app's gate compares it byte for
byte with the file it commits.

    python scripts/workflow_contract.py                  the TypeScript, on stdout
    python scripts/workflow_contract.py --write PATH     write it to PATH
    python scripts/workflow_contract.py --check PATH     exit 1 when PATH differs
    python scripts/workflow_contract.py --json           the declaration as data, for the app's gates

The app side: `npm run workflow:contract` (check) and `npm run workflow:contract -- --write`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from taktik.core.app.contract import WORKFLOW_CONTRACTS  # noqa: E402
from taktik.core.app.contract.schema import (  # noqa: E402
    HOST,
    Computed,
    Event,
    Field,
    ListOf,
    MapOf,
    OneOf,
    Shape,
    WorkflowContract,
    has_default,
)
from taktik.core.app.contract.shared import AI_SPEND_EVENT, ERROR_EVENT, STATUS_EVENT  # noqa: E402

#: Lines every bridge shares get one interface, referenced by each workflow.
SHARED_LINES = {
    STATUS_EVENT.type: ("BridgeStatusLine", STATUS_EVENT),
    ERROR_EVENT.type: ("BridgeErrorLine", ERROR_EVENT),
    AI_SPEND_EVENT.type: ("BridgeAiSpendLine", AI_SPEND_EVENT),
}

HEADER = """/**
 * GENERATED from the bot - do not edit: `npm run workflow:contract -- --write`.
 *
 * The bot/app contract as the bot declares it (`core/taktik/core/app/contract/`): for each declared
 * workflow, the settings its launcher reads (`<Name>Settings`, the defaults the bot applies when a
 * key is absent), the file its bridge reads (`<Name>BridgePayload`) and the stdout lines the app
 * reads (`<Name>BridgeLine`). Rendered by `core/scripts/workflow_contract.py`;
 * `npm run workflow:contract` fails when this file and the bot disagree.
 */
"""


# ------------------------------------------------------------------------------------ types


def ts_type(spec: Any) -> str:
    if isinstance(spec, str):
        return {"int": "number", "number": "number", "bool": "boolean", "string": "string", "json": "unknown"}[spec]
    if isinstance(spec, OneOf):
        return " | ".join(f"'{value}'" for value in spec.values)
    if isinstance(spec, ListOf):
        inner = ts_type(spec.item)
        return f"({inner})[]" if " | " in inner else f"{inner}[]"
    if isinstance(spec, MapOf):
        return f"Record<string, {ts_type(spec.value)}>"
    if isinstance(spec, Shape):
        return spec.name
    raise TypeError(f"unknown type spec: {spec!r}")


def field_type(item: Field) -> str:
    base = ts_type(item.type)
    return f"{base} | null" if item.nullable else base


def literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value) if not float(value).is_integer() else str(int(value))
    if isinstance(value, str):
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
    raise TypeError(f"no TypeScript literal for {value!r}")


def constant_name(name: str) -> str:
    return "_".join(token.upper() for token in re.findall(r"TikTok|[A-Z][a-z0-9]*", name))


def doc_line(item: Field) -> str:
    text = item.doc.strip()
    if has_default(item) and not isinstance(item.default, (tuple, list)):
        text += f" Default {literal(item.default)}."
    elif isinstance(item.default, Computed):
        text += f" Default: {item.default.description}."
    return text.replace("*/", "* /")


def member(item: Field, *, force_optional: Optional[bool] = None, indent: str = "  ") -> List[str]:
    optional = (not item.required) if force_optional is None else force_optional
    out = []
    text = doc_line(item)
    if text:
        out.append(f"{indent}/** {text} */")
    out.append(f"{indent}{item.key}{'?' if optional else ''}: {field_type(item)}")
    return out


def shapes_in(spec: Any) -> Iterable[Shape]:
    if isinstance(spec, Shape):
        for item in spec.fields:
            yield from shapes_in(item.type)
        yield spec
    elif isinstance(spec, ListOf):
        yield from shapes_in(spec.item)
    elif isinstance(spec, MapOf):
        yield from shapes_in(spec.value)


def app_settings(contract: WorkflowContract) -> List[Field]:
    return [item for item in contract.settings if item.app and item.by != HOST]


def host_settings(contract: WorkflowContract) -> List[Field]:
    return [item for item in contract.settings if item.app and item.by == HOST]


# ------------------------------------------------------------------------------------ render


def render_shape(shape: Shape) -> List[str]:
    out = [f"/** {shape.doc} */"] if shape.doc else []
    out.append(f"export interface {shape.name} {{")
    for item in shape.fields:
        out += member(item, force_optional=item.optional or not item.required and _is_setting_shape(shape))
    out.append("}")
    return out


def _is_setting_shape(shape: Shape) -> bool:
    """A shape the operator fills (the IP rotation) has optional members; a line's shape does not."""
    return all(has_default(item) for item in shape.fields)


def render_line(name: str, event: Event) -> List[str]:
    out = [f"/** `{event.type}`: {event.doc} */"] if event.doc else []
    out.append(f"export interface {name} {{")
    for item in event.fields:
        out += member(item, force_optional=item.optional)
    out.append("}")
    return out


def render_contract(contract: WorkflowContract) -> Tuple[List[str], List[str]]:
    name = contract.name
    reader = contract.reader.split(":")[-1]
    exported: List[str] = []
    out = [
        f"// {'-' * 96}",
        f"// {contract.workflow_id} ({contract.bridge})",
        "",
        f"/** {contract.doc} Read by `{reader}`, for the app and for a CLI run of `{contract.workflow_id}`"
        " (which also takes the aliases and the CLI-only keys of the declaration). */",
        f"export interface {name}Settings {{",
    ]
    for item in app_settings(contract):
        out += member(item)
    out.append("}")
    exported.append(f"{name}Settings")

    defaults = [item for item in app_settings(contract)
                if has_default(item) and not isinstance(item.default, (tuple, list))]
    if defaults:
        keys = " | ".join(f"'{item.key}'" for item in defaults)
        const = f"{constant_name(name)}_DEFAULTS"
        out += [
            "",
            "/** What the bot applies when a key is absent. */",
            f"export const {const}: Readonly<Required<Pick<{name}Settings, {keys}>>> = {{",
        ]
        out += [f"  {item.key}: {literal(item.default)}," for item in defaults]
        out.append("}")
        exported.append(const)

    beside = [item for item in contract.bridge_fields if item.key in contract.beside_settings]
    root = [item for item in contract.bridge_fields if item.key not in contract.beside_settings]
    hosts = host_settings(contract)
    out += ["", f"/** The file `{contract.bridge}` reads (its config file, sole argument). */"]
    if contract.nest:
        out.append(f"export interface {name}BridgePayload {{")
        for item in root:
            out += member(item)
        inner = [line for item in hosts + beside for line in member(item, force_optional=not item.required, indent="    ")]
        if inner:
            out.append(f"  {contract.nest}: {name}Settings & {{")
            out += inner
            out.append("  }")
        else:
            out.append(f"  {contract.nest}: {name}Settings")
        out.append("}")
    else:
        out.append(f"export interface {name}BridgePayload extends {name}Settings {{")
        for item in root + hosts + beside:
            out += member(item)
        out.append("}")
    exported.append(f"{name}BridgePayload")

    if contract.events:
        out += ["", f"/** The stdout lines of `{contract.bridge}` the app reads, by `type`. */",
                f"export interface {name}BridgeLines {{"]
        for event in contract.events:
            if event.type in SHARED_LINES and SHARED_LINES[event.type][1] is event:
                out.append(f"  {event.type}: {SHARED_LINES[event.type][0]}")
                continue
            out.append(f"  /** {event.doc} */")
            out.append(f"  {event.type}: {{")
            for item in event.fields:
                out += member(item, force_optional=item.optional, indent="    ")
            out.append("  }")
        out.append("}")
        out += ["", f"export type {name}BridgeLine = BridgeLine<{name}BridgeLines>"]
        exported += [f"{name}BridgeLines", f"{name}BridgeLine"]
    return out, exported


def render(contracts: Tuple[WorkflowContract, ...] = WORKFLOW_CONTRACTS) -> Tuple[str, List[str]]:
    lines = [HEADER.rstrip("\n"), ""]
    exported = ["BridgeLine"]
    lines += [
        "/** One stdout line of a bridge: its `type`, and the fields declared for that type. */",
        "export type BridgeLine<Lines> = { [K in keyof Lines]: { type: K } & Lines[K] }[keyof Lines]",
        "",
    ]
    shapes: Dict[str, Shape] = {}
    for contract in contracts:
        for item in (*contract.settings, *contract.bridge_fields, *(f for e in contract.events for f in e.fields)):
            for shape in shapes_in(item.type):
                if shapes.setdefault(shape.name, shape) != shape:
                    raise ValueError(f"two shapes named {shape.name}")
    for shape in shapes.values():
        lines += render_shape(shape) + [""]
        exported.append(shape.name)
    used = {event.type for contract in contracts for event in contract.events}
    for event_type, (name, event) in SHARED_LINES.items():
        if event_type in used:
            lines += render_line(name, event) + [""]
            exported.append(name)
    for contract in contracts:
        body, names = render_contract(contract)
        lines += body + [""]
        exported += names
    return "\n".join(lines).rstrip("\n") + "\n", exported


# ------------------------------------------------------------------------------------ data


def _paths(item: Field, prefix: Tuple[str, ...]) -> List[List[str]]:
    out = []
    for name in item.names:
        out.append([*prefix, name])
        if isinstance(item.type, Shape):
            for sub in item.type.fields:
                out += _paths(sub, (*prefix, name))
    return out


def as_data(contracts: Tuple[WorkflowContract, ...] = WORKFLOW_CONTRACTS) -> Dict[str, Any]:
    _, exported = render(contracts)
    workflows = {}
    for contract in contracts:
        nest = (contract.nest,) if contract.nest else ()
        launcher = [path for item in contract.settings for path in _paths(item, ())]
        bridge = [path for item in contract.settings for path in _paths(item, nest)]
        for item in contract.bridge_fields:
            bridge += _paths(item, nest if item.key in contract.beside_settings else ())
        if contract.nest:
            bridge.append([contract.nest])
        workflows[contract.workflow_id] = {
            "name": contract.name,
            "bridge": contract.bridge,
            "launcher": contract.launcher,
            "reader": contract.reader,
            "nest": contract.nest,
            "launcherReads": launcher,
            "bridgeReads": bridge,
            "settings": [
                {"key": item.key, "aliases": list(item.aliases), "app": item.app, "by": item.by,
                 "required": item.required}
                for item in contract.settings
            ],
            "bridgeFields": [
                {"key": item.key, "aliases": list(item.aliases), "by": item.by,
                 "beside": item.key in contract.beside_settings}
                for item in contract.bridge_fields
            ],
            "events": {event.type: [item.key for item in event.fields] for event in contract.events},
        }
    return {"workflows": workflows, "exports": exported}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", metavar="PATH")
    group.add_argument("--check", metavar="PATH")
    group.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.json:
        sys.stdout.write(json.dumps(as_data(), ensure_ascii=False) + "\n")
        return 0
    text, _ = render()
    if args.write:
        Path(args.write).write_text(text, encoding="utf-8", newline="\n")
        print(f"written: {args.write}")
        return 0
    if args.check:
        path = Path(args.check)
        current = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else ""
        if current != text:
            print(f"{args.check} is not the bot's contract: regenerate it (npm run workflow:contract -- --write)")
            return 1
        print(f"{args.check} matches the bot's contract")
        return 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
