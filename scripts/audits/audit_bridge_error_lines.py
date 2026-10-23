"""Ratchet gate: a bridge's broad `except` does not word its own `error` line.

A bridge that catches every exception and writes `send_error(f"Startup error: {exc}")` says the
failure in words of its own, with no code and no traceback: the app reads a generic crash, and two
bridges say the same cause two ways. The line of an exception has its shared functions:

* `crash_hooks.exception_event` (the code, the words and the traceback of an exception) and
  `entrypoint.send_import_error` (a module that did not import, `PYTHON_IMPORT_ERROR`);
* `run_bridge_main`, which says an exception that reaches it in the bridge's own shape (`CRASH`,
  with the traceback on stderr): a run that has nothing to add lets the exception rise;
* the bridge's emitter (`send_instagram_workflow_error`, `emit_dm_error`...), which owns the
  words and the code of its bridge.

The rule (read on the ``ast``, never on the text), under ``bridges/``:

* a handler is BROAD as for ``audit_swallowed_errors.py`` (bare, ``Exception``, ``BaseException``,
  alone or in a tuple);
* a broad handler WORDS ITS OWN LINE when its body (nested ``def``/``lambda``/``class`` excluded)
  emits an ``error`` line in words of its own: ``send_error(...)`` / ``_send_error(...)``; ``<x>.error(...)`` on
  an IPC or a notifier (a name containing ``ipc`` or ``notifier``; ``logger.error`` is a log, not
  a line); ``<x>.send("error", ...)``, ``send_message("error", ...)``, ``emit("error", ...)``; any
  call given a literal ``{"type": "error", ...}``. A line made of ``**exception_event(...)`` is the
  shared account, not words of its own.

Ratchet (``scripts/audits/ratchet.py``): ``scripts/audits/audit_bridge_error_lines_baseline.json``
names each function (``<file>::<Class.function>``) with its count of such handlers. The list only
goes down: a new handler of this kind, in a function the list does not name or above its count, is
red; a function the list names that no longer has one must leave the list (``--update-baseline``).

Usage:
    python scripts/audits/audit_bridge_error_lines.py                    # green / red
    python scripts/audits/audit_bridge_error_lines.py --list             # every handler, by file
    python scripts/audits/audit_bridge_error_lines.py --update-baseline  # record decreases only
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from audit_swallowed_errors import dotted_parts, is_broad_type, walk_body
from ratchet import Ratchet, enforce, read_source, relative, source_files

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = ("bridges",)
BASELINE = ROOT / "scripts" / "audits" / "audit_bridge_error_lines_baseline.json"

#: Functions that write an `error` line, whatever their arguments.
ERROR_SENDERS = {"send_error", "_send_error"}
#: Functions that write a line whose type is their first argument.
TYPED_SENDERS = {"send", "send_message", "emit", "_emit"}


@dataclass(frozen=True)
class Finding:
    path: str
    function: str
    line: int

    @property
    def key(self) -> str:
        return f"{self.path}::{self.function}"


def _names_a_channel(part: str) -> bool:
    name = part.lower()
    return "ipc" in name or "notifier" in name


def _is_error_type(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value == "error"


def _is_error_dict(node: ast.expr) -> bool:
    return isinstance(node, ast.Dict) and any(
        isinstance(key, ast.Constant) and key.value == "type" and _is_error_type(value)
        for key, value in zip(node.keys, node.values) if key is not None)


def _is_shared_account(call: ast.Call) -> bool:
    """`**exception_event(...)`: the line is the shared account of the exception."""
    return any(keyword.arg is None and isinstance(keyword.value, ast.Call)
               and dotted_parts(keyword.value.func)[:1] == ["exception_event"]
               for keyword in call.keywords)


def emits_error_line(call: ast.Call) -> bool:
    """Whether this call writes an `error` line on the bridge's stdout in words of its own."""
    if _is_shared_account(call):
        return False
    func = call.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
    if name in ERROR_SENDERS:
        return True
    if (name == "error" and isinstance(func, ast.Attribute)
            and any(_names_a_channel(part) for part in dotted_parts(func.value))):
        return True
    if name in TYPED_SENDERS and call.args and _is_error_type(call.args[0]):
        return True
    return any(_is_error_dict(arg) for arg in call.args)


def handler_words_its_own_line(handler: ast.ExceptHandler) -> bool:
    if not is_broad_type(handler.type):
        return False
    return any(isinstance(node, ast.Call) and emits_error_line(node) for node in walk_body(handler.body))


class _Scanner(ast.NodeVisitor):
    def __init__(self, path: str):
        self.path = path
        self.scope: List[str] = []
        self.findings: List[Finding] = []

    def _visit_scope(self, node) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_ClassDef = _visit_scope
    visit_FunctionDef = _visit_scope
    visit_AsyncFunctionDef = _visit_scope

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if handler_words_its_own_line(node):
            function = ".".join(self.scope) or "<module>"
            self.findings.append(Finding(self.path, function, node.lineno))
        self.generic_visit(node)


def scan_source(source: str, path: str = "<string>") -> List[Finding]:
    scanner = _Scanner(path)
    scanner.visit(ast.parse(source))
    return scanner.findings


def scan_findings(root: Optional[Path] = None) -> List[Finding]:
    root = root or ROOT
    return [finding for file in source_files(root, SCAN_ROOTS, (".py",))
            for finding in scan_source(read_source(file, root), relative(file, root))]


def scan_repository(root: Optional[Path] = None) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for finding in scan_findings(root):
        counts[finding.key] = counts.get(finding.key, 0) + 1
    return counts


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--list" in argv:
        findings = scan_findings()
        for finding in findings:
            print(f"  {finding.path}:{finding.line}  {finding.function}")
        print(f"\n{len(findings)} broad handler(s) of the bridges word their own error line.")
        return 0
    return enforce(scan_repository(), Ratchet(
        label="Bridge error lines",
        noun="handler(s) wording its own error line",
        remedy=("Let the exception rise to run_bridge_main, or say it through send_import_error, "
                "exception_event or the bridge's emitter."),
        command="python scripts/audits/audit_bridge_error_lines.py",
        baseline=BASELINE,
        unit="function",
    ), update="--update-baseline" in argv)


if __name__ == "__main__":
    raise SystemExit(main())
