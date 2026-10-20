#!/usr/bin/env python3
"""Render the bot/app contract (`taktik/core/contract/`) for the desktop app.

The app's types for the declared workflows are generated from the declaration, never written by
hand: the settings each workflow reads (their defaults, the bounds outside which its reader refuses
the run, and the same settings as data the app reads while it runs), the file its bridge reads, the
lines its bridge prints; the lines of the diagnostic tools; the catalogues of why a run ends (named
unions); the codes of a bridge's `error` line, with the key of each one's sentence in the app, and
those of them that are a refusal the run meant.
The output is deterministic (declaration order, no date), so the app's gate compares it byte for
byte with the file it commits.

    python scripts/audits/workflow_contract.py                  the TypeScript, on stdout
    python scripts/audits/workflow_contract.py --write PATH     write it to PATH
    python scripts/audits/workflow_contract.py --check PATH     exit 1 when PATH differs
    python scripts/audits/workflow_contract.py --json           the declaration as data, for the app's gates

The app side: `npm run workflow:contract` (check) and `npm run workflow:contract -- --write`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from taktik.core.contract import TOOL_CONTRACTS, WORKFLOW_CONTRACTS  # noqa: E402
from taktik.core.contract.bounds import describe  # noqa: E402
from taktik.core.contract.error_codes import BRIDGE_ERROR_CODE, BRIDGE_ERROR_PHRASES, BRIDGE_REFUSAL_CODES  # noqa: E402
from taktik.core.contract.schema import (  # noqa: E402
    HOST,
    Bounds,
    Computed,
    Event,
    Field,
    ListOf,
    MapOf,
    OneOf,
    Shape,
    ToolContract,
    WorkflowContract,
    nested_fields,
    scalar_default,
)
from taktik.core.contract.shared import (  # noqa: E402
    AI_COMMENT_DONE_EVENT,
    AI_COMMENT_START_EVENT,
    AI_ERROR_EVENT,
    AI_PROFILE_DONE_EVENT,
    AI_PROFILE_START_EVENT,
    AI_SCREENSHOT_DONE_EVENT,
    AI_SCREENSHOT_START_EVENT,
    AI_SPEND_EVENT,
    ERROR_EVENT,
    LOG_EVENT,
    NETWORK_RESET_COMPLETE_EVENT,
    SESSION_START_EVENT,
    STATUS_EVENT,
    STEP_METRIC_EVENT,
)
from taktik.core.contract.stop_reasons import CATALOGUES  # noqa: E402

#: Lines every bridge shares get one interface, referenced by each workflow.
SHARED_LINES = {
    STATUS_EVENT.type: ("BridgeStatusLine", STATUS_EVENT),
    ERROR_EVENT.type: ("BridgeErrorLine", ERROR_EVENT),
    AI_SPEND_EVENT.type: ("BridgeAiSpendLine", AI_SPEND_EVENT),
    LOG_EVENT.type: ("BridgeLogLine", LOG_EVENT),
    NETWORK_RESET_COMPLETE_EVENT.type: ("BridgeNetworkResetCompleteLine", NETWORK_RESET_COMPLETE_EVENT),
    SESSION_START_EVENT.type: ("BridgeSessionStartLine", SESSION_START_EVENT),
    STEP_METRIC_EVENT.type: ("BridgeStepMetricLine", STEP_METRIC_EVENT),
    AI_PROFILE_START_EVENT.type: ("BridgeAiProfileStartLine", AI_PROFILE_START_EVENT),
    AI_PROFILE_DONE_EVENT.type: ("BridgeAiProfileDoneLine", AI_PROFILE_DONE_EVENT),
    AI_SCREENSHOT_START_EVENT.type: ("BridgeAiScreenshotStartLine", AI_SCREENSHOT_START_EVENT),
    AI_SCREENSHOT_DONE_EVENT.type: ("BridgeAiScreenshotDoneLine", AI_SCREENSHOT_DONE_EVENT),
    AI_COMMENT_START_EVENT.type: ("BridgeAiCommentStartLine", AI_COMMENT_START_EVENT),
    AI_COMMENT_DONE_EVENT.type: ("BridgeAiCommentDoneLine", AI_COMMENT_DONE_EVENT),
    AI_ERROR_EVENT.type: ("BridgeAiErrorLine", AI_ERROR_EVENT),
}

HEADER = """/**
 * GENERATED from the bot - do not edit: `npm run workflow:contract -- --write`.
 *
 * The bot/app contract as the bot declares it (`core/taktik/core/contract/`): for each declared
 * workflow, the settings its launcher reads (`<Name>Settings`, `<NAME>_BOT_DEFAULTS` the defaults the
 * bot applies when a key is absent, `<NAME>_BOT_BOUNDS` the bounds outside which its reader refuses the
 * run before the phone is touched, `<NAME>_BOT_SETTINGS` the same settings as data, for code that reads
 * them while the app runs, `WORKFLOW_BOT_SETTINGS` by workflow of the manifest), the file its bridge reads
 * (`<Name>BridgePayload`) and the stdout lines the app reads (`<Name>BridgeLine`); the lines of the
 * diagnostic tools the app runs beside them; the catalogues of why a run ends, one union each; the codes
 * of a bridge's `error` line (`BridgeErrorCode`) and the key of each one's sentence in the app
 * (`BRIDGE_ERROR_PHRASE_KEYS`), and the codes of a refusal the run meant (`BRIDGE_REFUSAL_CODES`).
 * Rendered by `core/scripts/audits/workflow_contract.py`; `npm run workflow:contract` fails when this
 * file and the bot disagree.
 */
"""


# ------------------------------------------------------------------------------------ types


def ts_type(spec: Any) -> str:
    if isinstance(spec, str):
        return {"int": "number", "number": "number", "bool": "boolean", "string": "string", "json": "unknown"}[spec]
    if isinstance(spec, OneOf):
        named = [spec.name] if spec.name else [f"'{value}'" for value in spec.values]
        return " | ".join(named + (["''"] if spec.empty else []))
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
    return "_".join(token.upper() for token in re.findall(r"TikTok|YouTube|[A-Z][a-z0-9]*", name))


def served(contract: WorkflowContract) -> str:
    """The ids a CLI run takes: all of a family picked by a setting, the declared id otherwise."""
    ids = contract.serves if contract.selector else (contract.workflow_id,)
    return ", ".join(f"`{workflow_id}`" for workflow_id in ids)


def _one_of(value: Any) -> str:
    """A `when` value: one literal, or a tuple of them (any of its values)."""
    return " or ".join(literal(v) for v in value) if isinstance(value, tuple) else literal(value)


def _conditions(when) -> str:
    return ", ".join(f"`{key}` is {_one_of(value)}" for key, value in when.items())


def doc_line(item: Field) -> str:
    text = item.doc.strip()
    if scalar_default(item):
        text += f" Default {literal(item.default)}."
    elif isinstance(item.default, Computed):
        text += f" Default: {item.default.description}."
    if item.bounds is not None:
        scope = f" when {_conditions(item.bounds.when)}" if item.bounds.when else ""
        text += f" Bounds: {describe(item.bounds)}{scope}."
    if item.when:
        text += f" Read when {_conditions(item.when)}."
    return text.replace("*/", "* /")


def member(item: Field, *, force_optional: Optional[bool] = None, indent: str = "  ") -> List[str]:
    optional = (not item.required) if force_optional is None else force_optional
    out = []
    text = doc_line(item)
    if text:
        out.append(f"{indent}/** {text} */")
    out.append(f"{indent}{item.key}{'?' if optional else ''}: {field_type(item)}")
    return out


def catalogues_in(spec: Any) -> Iterable[OneOf]:
    """The named closed sets a type refers to, nested ones included."""
    if isinstance(spec, OneOf) and spec.name:
        yield spec
    elif isinstance(spec, Shape):
        for item in spec.fields:
            yield from catalogues_in(item.type)
    elif isinstance(spec, ListOf):
        yield from catalogues_in(spec.item)
    elif isinstance(spec, MapOf):
        yield from catalogues_in(spec.value)


def render_catalogue(catalogue: OneOf) -> List[str]:
    out = [f"/** {catalogue.doc} */"] if catalogue.doc else []
    out.append(f"export type {catalogue.name} =")
    out += [f"  | '{value}'" for value in catalogue.values]
    return out


def render_error_phrases() -> List[str]:
    """`BRIDGE_ERROR_PHRASE_KEYS`: for each code of a bridge's `error` line, the key of its sentence."""
    out = ["/** The key of each code's sentence in the app's translations (`sessionLive`): `contract/error_codes.py`. */",
           f"export const BRIDGE_ERROR_PHRASE_KEYS: Readonly<Record<{BRIDGE_ERROR_CODE.name}, string>> = {{"]
    out += [f"  {ts_key(code)}: {literal(key)}," for code, key in BRIDGE_ERROR_PHRASES.items()]
    out.append("}")
    return out


def render_refusal_codes() -> List[str]:
    """`BRIDGE_REFUSAL_CODES`: the codes of a refusal the run meant, which the app files no crash report for."""
    out = ["/** The codes of a refusal the run meant (no network, the app not on the phone): no crash report. */",
           f"export const BRIDGE_REFUSAL_CODES: readonly {BRIDGE_ERROR_CODE.name}[] = ["]
    out += [f"  {literal(code)}," for code in BRIDGE_REFUSAL_CODES]
    out.append("]")
    return out


def lines_interface(name: str, bridge: str, events: Tuple[Event, ...]) -> List[str]:
    """`<Name>BridgeLines`, one member per `type`, and the union `<Name>BridgeLine`."""
    out = ["", f"/** The stdout lines of `{bridge}` the app reads, by `type`. */",
           f"export interface {name}BridgeLines {{"]
    for event in events:
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


def render_shape(shape: Shape, setting: bool) -> List[str]:
    """A shape the app fills (settings, the IP rotation) has optional members; a line's shape does not."""
    out = [f"/** {shape.doc} */"] if shape.doc else []
    out.append(f"export interface {shape.name} {{")
    for item in shape.fields:
        if setting and not item.app:
            continue
        out += member(item, force_optional=not item.required if setting else item.optional)
    out.append("}")
    return out


def shape_defaults(shape: Shape) -> List[str]:
    """What the bot applies when a key of a nested setting is absent."""
    defaults = [item for item in shape.fields
                if item.app and scalar_default(item)]
    if not defaults:
        return []
    keys = " | ".join(f"'{item.key}'" for item in defaults)
    out = ["", "/** What the bot applies when a key is absent. */",
           f"export const {constant_name(shape.name)}_BOT_DEFAULTS: Readonly<Required<Pick<{shape.name}, {keys}>>> = {{"]
    out += [f"  {item.key}: {literal(item.default)}," for item in defaults]
    out.append("}")
    return out


#: The shape of one setting's bounds in the app, rendered once when a declaration has settings.
SETTING_BOUNDS = """/** The settings under which a key is read or its bounds hold, by dotted path (a list: any of its values). */
export type SettingCondition = Readonly<Record<string, string | number | boolean | ReadonlyArray<string | number | boolean>>>

/**
 * The bounds of a setting, as the bot declares them (`Field.bounds`): outside them, its reader refuses
 * the run before the phone is touched. A value absent or null is not held to them.
 */
export interface SettingBounds {
  /** The least number, included. */
  minimum?: number
  /** The greatest number, included. */
  maximum?: number
  /** The number that says "no limit", accepted beside the minimum and the maximum. */
  unboundedAt?: number
  /** The fewest items of a list. */
  minItems?: number
  /** The most items of a list. */
  maxItems?: number
  /** The most characters of a text, or of each text of a list. */
  maxLength?: number
  /** The settings under which the bounds hold; absent: always. */
  when?: SettingCondition
}"""

#: The settings as data, rendered once beside `SettingBounds`: the types of a TypeScript interface
#: vanish when the app is built, and code that reads the contract while the app runs (the parameters
#: of a tool, a planned step's settings) needs them.
SETTINGS_DECLARATION = """/** A setting's type as the bot declares it: a scalar, one of a closed set, a list, an object keyed by data, a nested setting. */
export type SettingType =
  | 'int'
  | 'number'
  | 'bool'
  | 'string'
  | 'json'
  | { readonly oneOf: readonly string[]; readonly empty?: true }
  | { readonly listOf: SettingType }
  | { readonly mapOf: SettingType }
  | { readonly shape: SettingsDeclaration }

/** One setting as data: its type, the comment of its member, and who fills it. */
export interface SettingDeclaration {
  readonly type: SettingType
  readonly doc: string
  /** The run is refused without it. */
  readonly required?: true
  /** It may be null. */
  readonly nullable?: true
  /** The host process fills it (an API key, the warmup caps), never the operator. */
  readonly host?: true
  /** The settings under which the reader reads it. */
  readonly when?: SettingCondition
}

/** The settings of a workflow or of a nested setting as data, with the bot's defaults and bounds. */
export interface SettingsDeclaration {
  readonly fields: Readonly<Record<string, SettingDeclaration>>
  readonly defaults: Readonly<Record<string, string | number | boolean>>
  readonly bounds: Readonly<Record<string, SettingBounds>>
}

/** A `SettingsDeclaration` held to its interface: one entry per member, no other. */
export interface BotSettings<S> extends SettingsDeclaration {
  readonly fields: { readonly [K in keyof Required<S> & string]: SettingDeclaration }
}

/** What a workflow of the manifest reads: the settings of its declaration, and its value of the declaration's selector. */
export interface WorkflowBotSettings {
  readonly settings: SettingsDeclaration
  /** Absent when the declaration serves one workflow: the selector, if any, is then a setting like the others. */
  readonly selector?: { readonly key: string; readonly value: string }
}"""

_IDENTIFIER = re.compile(r"^[A-Za-z_$][\w$]*$")


def ts_key(name: str) -> str:
    return name if _IDENTIFIER.match(name) else literal(name)


def ts_when(when) -> str:
    """A `when` (of a setting or of its bounds) as a TypeScript object literal."""
    inner = ", ".join(
        f"{ts_key(name)}: "
        f"{'[' + ', '.join(literal(v) for v in wanted) + ']' if isinstance(wanted, list) else literal(wanted)}"
        for name, wanted in _json_when(when).items())
    return f"{{ {inner} }}"


def bounds_data(bounds: Bounds) -> Dict[str, Any]:
    """The bounds as the app reads them: camelCase, the ones declared only."""
    data: Dict[str, Any] = {key: value for key, value in (
        ("minimum", bounds.minimum),
        ("maximum", bounds.maximum),
        ("unboundedAt", bounds.unbounded_at),
        ("minItems", bounds.min_items),
        ("maxItems", bounds.max_items),
        ("maxLength", bounds.max_length),
    ) if value is not None}
    if bounds.when:
        data["when"] = _json_when(bounds.when)
    return data


def ts_bounds(bounds: Bounds) -> str:
    parts = [f"when: {ts_when(bounds.when)}" if key == "when" else f"{key}: {literal(value)}"
             for key, value in bounds_data(bounds).items()]
    return "{ " + ", ".join(parts) + " }"


def bounds_constant(const: str, type_name: str, fields: Iterable[Field]) -> List[str]:
    """`<NAME>_BOT_BOUNDS`: the bounds of the settings of `type_name` that have some."""
    bounded = [item for item in fields if item.app and item.bounds is not None]
    if not bounded:
        return []
    keys = " | ".join(f"'{item.key}'" for item in bounded)
    out = ["", "/** Outside these bounds, the bot's reader refuses the run before the phone is touched. */",
           f"export const {const}: Readonly<Record<keyof Pick<{type_name}, {keys}>, SettingBounds>> = {{"]
    out += [f"  {item.key}: {ts_bounds(item.bounds)}," for item in bounded if item.bounds is not None]
    out.append("}")
    return out


def ts_setting_type(spec: Any) -> str:
    """A type spec as data (`SettingType`); a nested setting names its own `<SHAPE>_BOT_SETTINGS`."""
    if isinstance(spec, str):
        return literal(spec)
    if isinstance(spec, OneOf):
        values = ", ".join(literal(value) for value in spec.values)
        return f"{{ oneOf: [{values}]{', empty: true' if spec.empty else ''} }}"
    if isinstance(spec, ListOf):
        return f"{{ listOf: {ts_setting_type(spec.item)} }}"
    if isinstance(spec, MapOf):
        return f"{{ mapOf: {ts_setting_type(spec.value)} }}"
    if isinstance(spec, Shape):
        return f"{{ shape: {constant_name(spec.name)}_BOT_SETTINGS }}"
    raise TypeError(f"unknown type spec: {spec!r}")


def ts_setting(item: Field) -> str:
    """One setting as data (`SettingDeclaration`); its documentation is the comment of its member."""
    parts = [f"type: {ts_setting_type(item.type)}", f"doc: {literal(doc_line(item))}"]
    if item.required:
        parts.append("required: true")
    if item.nullable:
        parts.append("nullable: true")
    if item.by == HOST:
        parts.append("host: true")
    if item.when:
        parts.append(f"when: {ts_when(item.when)}")
    return "{ " + ", ".join(parts) + " }"


def settings_constant(prefix: str, type_name: str, fields: Iterable[Field],
                      defaults: bool, bounds: bool) -> List[str]:
    """`<NAME>_BOT_SETTINGS`: the members of `type_name` as data, beside its defaults and bounds constants."""
    out = ["", f"/** `{type_name}` as data, for code that reads it while the app runs. */",
           f"export const {prefix}_BOT_SETTINGS: BotSettings<{type_name}> = {{",
           "  fields: {"]
    out += [f"    {ts_key(item.key)}: {ts_setting(item)}," for item in fields]
    out += ["  },",
            f"  defaults: {f'{prefix}_BOT_DEFAULTS' if defaults else '{}'},",
            f"  bounds: {f'{prefix}_BOT_BOUNDS' if bounds else '{}'},",
            "}"]
    return out


def selector_value(contract: WorkflowContract, workflow_id: str) -> Optional[str]:
    """The value of the declaration's selector that picks `workflow_id`: its last segment
    (`instagram.automation.<workflowType>`), when the declaration serves several ids. One declaration
    for one id (the notifications and their commands) keeps its selector as a setting."""
    if not contract.selector or not contract.also:
        return None
    value = workflow_id.rsplit(".", 1)[-1]
    allowed = contract.setting(contract.selector).type
    if not (isinstance(allowed, OneOf) and allowed.allows(value)):
        raise ValueError(f"{workflow_id}: `{value}` is no value of the selector `{contract.selector}`")
    return value


def workflow_settings_index(contracts: Tuple[WorkflowContract, ...]) -> Tuple[List[str], List[str]]:
    """`DeclaredWorkflowId` and `WORKFLOW_BOT_SETTINGS`: for each workflow of the manifest a declaration
    serves, its settings and its value of the selector."""
    entries: Dict[str, str] = {}
    for contract in contracts:
        for workflow_id in contract.serves:
            if workflow_id in entries:
                raise ValueError(f"{workflow_id} is served by two declarations")
            value = selector_value(contract, workflow_id)
            picked = "" if value is None else (
                f", selector: {{ key: {literal(contract.selector)}, value: {literal(value)} }}")
            entries[workflow_id] = f"{{ settings: {constant_name(contract.name)}_BOT_SETTINGS{picked} }}"
    out = [f"// {'-' * 96}", "// the declared workflows of the manifest, as data", "",
           "/** Every workflow of the manifest the bot declares. */",
           "export type DeclaredWorkflowId ="]
    out += [f"  | {literal(workflow_id)}" for workflow_id in entries]
    out += ["", "/** For each declared workflow, the settings it reads, as data. */",
            "export const WORKFLOW_BOT_SETTINGS: Readonly<Record<DeclaredWorkflowId, WorkflowBotSettings>> = {"]
    out += [f"  {literal(workflow_id)}: {entry}," for workflow_id, entry in entries.items()]
    out.append("}")
    return out, ["DeclaredWorkflowId", "WORKFLOW_BOT_SETTINGS"]


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
    picked = f", picked by `{contract.selector}`" if contract.selector else ""
    out = [
        f"// {'-' * 96}",
        f"// {contract.workflow_id} ({contract.bridge})",
        "",
        f"/** {contract.doc} Read by `{reader}`, for the app and for a CLI run of {served(contract)}{picked}"
        " (which also takes the aliases and the CLI-only keys of the declaration). */",
        f"export interface {name}Settings {{",
    ]
    for item in app_settings(contract):
        out += member(item)
    out.append("}")
    exported.append(f"{name}Settings")

    defaults = [item for item in app_settings(contract) if scalar_default(item)]
    if defaults:
        keys = " | ".join(f"'{item.key}'" for item in defaults)
        const = f"{constant_name(name)}_BOT_DEFAULTS"
        out += [
            "",
            "/** What the bot applies when a key is absent. */",
            f"export const {const}: Readonly<Required<Pick<{name}Settings, {keys}>>> = {{",
        ]
        out += [f"  {item.key}: {literal(item.default)}," for item in defaults]
        out.append("}")
        exported.append(const)

    bounds_const = f"{constant_name(name)}_BOT_BOUNDS"
    bounds = bounds_constant(bounds_const, f"{name}Settings", app_settings(contract))
    if bounds:
        out += bounds
        exported.append(bounds_const)

    out += settings_constant(constant_name(name), f"{name}Settings", app_settings(contract),
                             defaults=bool(defaults), bounds=bool(bounds))
    exported.append(f"{constant_name(name)}_BOT_SETTINGS")

    beside =[item for item in contract.bridge_fields if item.key in contract.beside_settings]
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
        out += lines_interface(name, contract.bridge, contract.events)
        exported += [f"{name}BridgeLines", f"{name}BridgeLine"]
    return out, exported


def render_tool(tool: ToolContract) -> Tuple[List[str], List[str]]:
    mode = f", when its file sets `{tool.mode}`" if tool.mode else ""
    out = [
        f"// {'-' * 96}",
        f"// tool {tool.name} ({tool.bridge}{mode})",
        "",
        f"/** {tool.doc} Outside the workflow manifest: only its lines are declared. */",
    ]
    out += lines_interface(tool.name, tool.bridge, tool.events)[2:]
    return out, [f"{tool.name}BridgeLines", f"{tool.name}BridgeLine"]


def render(contracts: Tuple[WorkflowContract, ...] = WORKFLOW_CONTRACTS,
           tools: Tuple[ToolContract, ...] = TOOL_CONTRACTS) -> Tuple[str, List[str]]:
    lines = [HEADER.rstrip("\n"), ""]
    exported = ["BridgeLine"]
    lines += [
        "/** One stdout line of a bridge: its `type`, and the fields declared for that type. */",
        "export type BridgeLine<Lines> = { [K in keyof Lines]: { type: K } & Lines[K] }[keyof Lines]",
        "",
    ]
    if contracts:
        lines += [SETTING_BOUNDS, "", SETTINGS_DECLARATION, ""]
        exported += ["SettingCondition", "SettingBounds", "SettingType", "SettingDeclaration", "SettingsDeclaration",
                     "BotSettings", "WorkflowBotSettings"]
    shapes: Dict[str, Shape] = {}
    catalogues: Dict[str, OneOf] = {catalogue.name: catalogue for catalogue in (*CATALOGUES, BRIDGE_ERROR_CODE)}
    settings: set = set()
    filled: set = set()
    every_field = [
        *(item for contract in contracts
          for item in (*contract.settings, *contract.bridge_fields, *(f for e in contract.events for f in e.fields))),
        *(item for tool in tools for event in tool.events for item in event.fields),
    ]
    for item in every_field:
        for shape in shapes_in(item.type):
            if shapes.setdefault(shape.name, shape) != shape:
                raise ValueError(f"two shapes named {shape.name}")
        for catalogue in catalogues_in(item.type):
            if catalogues.setdefault(catalogue.name, catalogue).values != catalogue.values:
                raise ValueError(f"two closed sets named {catalogue.name}")
    for contract in contracts:
        for item in (*contract.settings, *contract.bridge_fields):
            filled |= {shape.name for shape in shapes_in(item.type)}
        for item in contract.settings:
            settings |= {shape.name for shape in shapes_in(item.type)}
    for catalogue in catalogues.values():
        lines += render_catalogue(catalogue) + [""]
        exported.append(catalogue.name)
    lines += render_error_phrases() + [""]
    exported.append("BRIDGE_ERROR_PHRASE_KEYS")
    lines += render_refusal_codes() + [""]
    exported.append("BRIDGE_REFUSAL_CODES")
    for shape in shapes.values():
        lines += render_shape(shape, shape.name in filled)
        if shape.name in settings:
            defaults = shape_defaults(shape)
            lines += defaults
            if defaults:
                exported.append(f"{constant_name(shape.name)}_BOT_DEFAULTS")
            bounds_const = f"{constant_name(shape.name)}_BOT_BOUNDS"
            bounds = bounds_constant(bounds_const, shape.name, shape.fields)
            lines += bounds
            if bounds:
                exported.append(bounds_const)
            lines += settings_constant(constant_name(shape.name), shape.name,
                                       [item for item in shape.fields if item.app],
                                       defaults=bool(defaults), bounds=bool(bounds))
            exported.append(f"{constant_name(shape.name)}_BOT_SETTINGS")
        lines.append("")
        exported.append(shape.name)
    used = {event.type for owner in (*contracts, *tools) for event in owner.events}
    for event_type, (name, event) in SHARED_LINES.items():
        if event_type in used:
            lines += render_line(name, event) + [""]
            exported.append(name)
    for contract in contracts:
        body, names = render_contract(contract)
        lines += body + [""]
        exported += names
    if contracts:
        body, names = workflow_settings_index(contracts)
        lines += body + [""]
        exported += names
    for tool in tools:
        body, names = render_tool(tool)
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


def _json_paths(item: Field, prefix: Tuple[str, ...] = ()) -> List[List[str]]:
    """Where an object read as a whole sits, nested in a shape or not: below it, nothing is declared."""
    out = []
    for name in item.names:
        if item.type == "json":
            out.append([*prefix, name])
        elif isinstance(item.type, Shape):
            for sub in item.type.fields:
                out += _json_paths(sub, (*prefix, name))
    return out


def _json_when(when) -> Dict[str, Any]:
    return {key: list(value) if isinstance(value, tuple) else value for key, value in (when or {}).items()}


def as_data(contracts: Tuple[WorkflowContract, ...] = WORKFLOW_CONTRACTS,
            tools: Tuple[ToolContract, ...] = TOOL_CONTRACTS) -> Dict[str, Any]:
    _, exported = render(contracts, tools)
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
            "serves": list(contract.serves),
            "selector": contract.selector,
            "bridge": contract.bridge,
            "also": list(contract.also),
            "launcher": contract.launcher,
            "reader": contract.reader,
            "nest": contract.nest,
            "launcherReads": launcher,
            "bridgeReads": bridge,
            # Objects the bot reads as a whole ("json"): what lies below them is not declared yet.
            "opaque": [[*nest, *path] for item in contract.settings for path in _json_paths(item)],
            "launcherOpaque": [path for item in contract.settings for path in _json_paths(item)],
            # `when`: the settings under which the reader reads the key (a list: any of its values).
            "settings": [
                {"key": item.key, "aliases": list(item.aliases), "app": item.app, "by": item.by,
                 "required": item.required, "when": _json_when(item.when)}
                for item in contract.settings
            ],
            "bridgeFields": [
                {"key": item.key, "aliases": list(item.aliases), "by": item.by,
                 "beside": item.key in contract.beside_settings}
                for item in contract.bridge_fields
            ],
            "events": {event.type: [item.key for item in event.fields] for event in contract.events},
            # What the reader refuses before the phone, by setting path (wire keys); `when` the
            # bounds' own condition, beside the setting's.
            "bounds": [
                {"path": list(path), **bounds_data(item.bounds)}
                for path, item, _, _ in nested_fields(contract.settings) if item.bounds is not None
            ],
        }
    # An id that shares a declaration (`also`) reads the same file: the gates look it up by id.
    for contract in contracts:
        for workflow_id in contract.also:
            workflows[workflow_id] = {**workflows[contract.workflow_id], "sameAs": contract.workflow_id}
    tool_data = {
        tool.name: {
            "bridge": tool.bridge,
            "mode": tool.mode,
            "events": {event.type: [item.key for item in event.fields] for event in tool.events},
        }
        for tool in tools
    }
    catalogues = {catalogue.name: list(catalogue.values) for catalogue in (*CATALOGUES, BRIDGE_ERROR_CODE)}
    return {"workflows": workflows, "tools": tool_data, "catalogues": catalogues,
            "errorPhrases": dict(BRIDGE_ERROR_PHRASES), "exports": exported}


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
