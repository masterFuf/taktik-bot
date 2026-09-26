"""Census of the JSON events the bot writes on stdout for the desktop app.

A bridge talks to the app through JSON lines whose ``type`` names the event. This
audit reads the sources (never runs them) and lists every ``type`` the bot can
emit, with where. The desktop app's quality gate (``npm run bridge:events``)
reads that list with ``--json`` and fails when an emitted type has no reader in
the app, or when the app reads a type the bot never emits.

A type counts as emitted when it is written as a literal at an emission point:

- ``ipc.send("x", ...)`` and the other sender calls in ``SINKS`` (the literal sits
  at the position given there);
- ``_emit(notifier, "send", "x", ...)``, the notifier indirection;
- a ``{"type": "x", ...}`` dict handed to a call that prints, emits, writes or
  sends it, directly or through a variable of the same function.

Standalone, the audit fails when an emission point carries a type it cannot read
statically (a variable that is neither a module constant nor the parameter of a
declared forwarder): the app gate would be blind to it.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("bridges", "taktik")

EVENT_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")

# (call form, callee name) -> position of the event type among positional args.
SINKS: dict[tuple[str, str], int] = {
    ("attr", "send"): 0,
    ("name", "send_message"): 0,
    ("attr", "_send_ipc"): 0,
    ("attr", "_send_to_desktop"): 0,
    ("name", "notify"): 1,
    ("name", "_notify"): 1,
}

# Functions that receive an event type and pass it on to a sink. Their callers are
# the ones that carry the literal.
FORWARDERS = {
    "send": "IPC.send, the stdout writer",
    "send_message": "bridge_base.send_message, module facade over IPC.send",
    "_send_ipc": "UI watchdog, guarded IPC.send",
    "_send_to_desktop": "MediaCaptureService, callback towards the bridge",
    "notify": "TikTok agent runtime, notifier.send or named callback",
    "_notify": "TikTok outreach, notifier.send or named callback",
    "on_media_event": "media capture bridge, fed by MediaCaptureService._send_to_desktop",
}

# A dict reaches stdout when it is handed to a call with one of these words in its name.
EMITTING_CALL = re.compile(r"emit|print|send|write|notify|publish", re.IGNORECASE)


def _callee(node: ast.Call) -> tuple[str, str] | None:
    func = node.func
    if isinstance(func, ast.Attribute):
        return ("attr", func.attr)
    if isinstance(func, ast.Name):
        return ("name", func.id)
    return None


def _str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


class _FileScan:
    def __init__(self, rel: str, tree: ast.Module) -> None:
        self.rel = rel
        self.tree = tree
        self.parent: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parent[child] = node
        self.constants = {
            target.id: node.value.value
            for node in tree.body
            if isinstance(node, ast.Assign) and _str(node.value) is not None
            for target in node.targets
            if isinstance(target, ast.Name)
        }

    def function_of(self, node: ast.AST) -> ast.AST | None:
        current = self.parent.get(node)
        while current is not None and not isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            current = self.parent.get(current)
        return current

    def resolve(self, node: ast.AST) -> tuple[list[str], bool]:
        """(literal types, forwarded). Forwarded = parameter of a declared forwarder."""
        literal = _str(node)
        if literal is not None:
            return [literal], False
        if not isinstance(node, ast.Name):
            return [], False
        if node.id in self.constants:
            return [self.constants[node.id]], False
        func = self.function_of(node)
        if isinstance(func, ast.Lambda):
            # `lambda x, event_type=event_type: ...` binds the loop variable of a table.
            args = func.args
            defaults = dict(zip([a.arg for a in args.args][-len(args.defaults):], args.defaults)) if args.defaults else {}
            if isinstance(defaults.get(node.id), ast.Name):
                return self.resolve_loop_variable(defaults[node.id]), False
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)) and func.name in FORWARDERS:
            params = {a.arg for a in func.args.args + func.args.posonlyargs + func.args.kwonlyargs}
            if node.id in params:
                return [], True
        return self.resolve_loop_variable(node), False

    def resolve_loop_variable(self, node: ast.Name) -> list[str]:
        """Types of `for a, event_type, b in TABLE`, TABLE a literal tuple of tuples in the function."""
        func = self.function_of(node)
        while isinstance(func, ast.Lambda):
            func = self.function_of(func)
        func = func or self.tree
        for loop in ast.walk(func):
            if not isinstance(loop, ast.For) or not isinstance(loop.target, ast.Tuple):
                continue
            names = [elt.id if isinstance(elt, ast.Name) else None for elt in loop.target.elts]
            if node.id not in names or not isinstance(loop.iter, ast.Name):
                continue
            index = names.index(node.id)
            for assign in ast.walk(func):
                if (isinstance(assign, ast.Assign) and len(assign.targets) == 1
                        and isinstance(assign.targets[0], ast.Name) and assign.targets[0].id == loop.iter.id
                        and isinstance(assign.value, (ast.Tuple, ast.List))):
                    rows = [row for row in assign.value.elts if isinstance(row, (ast.Tuple, ast.List))]
                    values = [_str(row.elts[index]) for row in rows if len(row.elts) > index]
                    if values and all(value is not None for value in values):
                        return values
        return []

    def reaches_emitting_call(self, node: ast.AST) -> bool:
        current, child = self.parent.get(node), node
        while isinstance(current, (ast.Call, ast.keyword, ast.Starred)):
            if isinstance(current, ast.Call) and child is not current.func:
                callee = _callee(current)
                if callee and EMITTING_CALL.search(callee[1]):
                    return True
            current, child = self.parent.get(current), current
        return False

    def name_emitted_in_function(self, name: str, anchor: ast.AST) -> bool:
        func = self.function_of(anchor) or self.tree
        for node in ast.walk(func):
            if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load):
                if self.reaches_emitting_call(node):
                    return True
        return False

    def dict_is_emitted(self, node: ast.Dict) -> bool:
        holder = self.parent.get(node)
        if self.reaches_emitting_call(node):
            return True
        if isinstance(holder, ast.Assign) and len(holder.targets) == 1 and isinstance(holder.targets[0], ast.Name):
            return self.name_emitted_in_function(holder.targets[0].id, holder)
        if isinstance(holder, ast.AnnAssign) and isinstance(holder.target, ast.Name):
            return self.name_emitted_in_function(holder.target.id, holder)
        return False


def scan(root: Path = ROOT) -> tuple[dict[str, list[str]], list[str]]:
    """Return ({event type: [file:line]}, [unresolved emission points])."""
    emitted: dict[str, list[str]] = defaultdict(list)
    unresolved: list[str] = []
    for folder in SCANNED:
        for path in sorted((root / folder).rglob("*.py")):
            scan_source(path.read_text(encoding="utf-8-sig"), path.relative_to(root).as_posix(), emitted, unresolved)
    return dict(emitted), unresolved


def scan_source(source: str, rel: str, emitted=None, unresolved=None):
    """Scan one module; returns the (emitted, unresolved) it filled."""
    emitted = defaultdict(list) if emitted is None else emitted
    unresolved = [] if unresolved is None else unresolved
    _scan_file(_FileScan(rel, ast.parse(source)), emitted, unresolved)
    return emitted, unresolved


def _record(scan_file: _FileScan, node: ast.AST, type_node: ast.AST, emitted, unresolved) -> None:
    where = f"{scan_file.rel}:{node.lineno}"
    literals, forwarded = scan_file.resolve(type_node)
    if literals:
        for literal in literals:
            if EVENT_NAME.match(literal):
                emitted[literal].append(where)
        return
    if not forwarded:
        unresolved.append(f"{where}: {ast.unparse(type_node)}")


def _scan_file(scan_file: _FileScan, emitted, unresolved) -> None:
    for node in ast.walk(scan_file.tree):
        if isinstance(node, ast.Call):
            callee = _callee(node)
            if callee == ("name", "_emit") and len(node.args) >= 3 and _str(node.args[1]) == "send":
                _record(scan_file, node, node.args[2], emitted, unresolved)
            elif callee in SINKS and len(node.args) > SINKS[callee]:
                _record(scan_file, node, node.args[SINKS[callee]], emitted, unresolved)
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if _str(key) == "type" and scan_file.dict_is_emitted(node):
                    _record(scan_file, node, value, emitted, unresolved)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print {type: [file:line]} for the app gate")
    args = parser.parse_args(argv)

    emitted, unresolved = scan()
    if args.json:
        print(json.dumps({"emitted": emitted, "unresolved": unresolved}, sort_keys=True))
        return 1 if unresolved else 0

    if not emitted:
        print(f"Bridge events audit failed: no event found under {ROOT}")
        return 1
    if unresolved:
        print("Bridge events audit failed: event type not readable statically")
        for item in unresolved:
            print(f" - {item}")
        print("\nWrite the type as a literal, a module constant, or declare the forwarder in FORWARDERS.")
        return 1
    print(f"Bridge events OK: {len(emitted)} event types, all written as literals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
