"""Ratchet gate: the number of swallowed errors per file may only go down.

Several of the worst bugs of the project were silent: a bio that was not read for two weeks
without one error line, a default value taken for a measure. Both came from an ``except`` that
neither logged nor re-raised.

The rule (read on the ``ast``, never on the text):

* A handler is BROAD when it is a bare ``except:``, or when its type is ``Exception`` or
  ``BaseException`` (``builtins.`` prefix allowed), alone or anywhere in a tuple
  (``except (ValueError, Exception):`` is broad: the tuple catches everything).
* A targeted handler (``except ValueError:``, ``except (KeyError, IndexError):``) is admitted even
  when its body is ``pass``: naming the expected failure is the decision, and it stays readable.
* A broad handler REPORTS when its body (nested ``def``/``lambda``/``class`` excluded) contains any
  of:
    - a ``raise`` (re-raise or translated error);
    - a logging call: ``<x>.debug/info/warning/warn/error/exception/critical/log(...)`` where one
      part of ``<x>`` names a logger (``log``, ``logging``, or a name containing ``logger``:
      ``self.logger``, ``_logger``, ``logger_to_use``...) or the app notifier (a name containing
      ``notifier`` or ``ipc``, which sends the line to the app); a helper called ``log(...)``,
      ``_log(...)`` or ``log_<x>(...)``; ``warnings.warn(...)``; ``print(..., file=sys.stderr)``;
      ``traceback.print_exc()`` / ``traceback.print_exception(...)``;
    - a use of the bound exception (``except Exception as exc:`` and ``exc`` is read): the error
      is carried on, returned, stored or emitted, which is the marked failure value.
* A broad handler that does none of these SWALLOWS. That covers the obvious bodies (``pass``,
  ``continue``, ``break``, ``return``, ``return None``, ``...``) and the default value dressed as a
  measure (``return 0``, ``return []``, ``x = False``) that says nothing.

Ratchet (``scripts/audits/ratchet.py``, shared by the counting gates):
``scripts/audits/audit_swallowed_errors_baseline.json`` maps each file to its count. The gate is red when
a file exceeds its count, when a file absent from the baseline swallows, and when a count in the
baseline is higher than reality (lower the baseline: the ratchet never goes back up).
``--update-baseline`` rewrites the baseline only when every count goes down or stays (it creates
the file, freezing the current state, only when the file does not exist).

Usage:
    python scripts/audits/audit_swallowed_errors.py                    # green / red
    python scripts/audits/audit_swallowed_errors.py --list             # totals, zones, heaviest files
    python scripts/audits/audit_swallowed_errors.py --update-baseline  # record decreases only
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from ratchet import Ratchet, enforce, print_listing, read_source, relative, source_files

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = ("taktik", "bridges")
BASELINE = ROOT / "scripts" / "audits" / "audit_swallowed_errors_baseline.json"

BROAD_NAMES = {"Exception", "BaseException"}
LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int


def _is_broad_type(node: Optional[ast.expr]) -> bool:
    if node is None:
        return True
    if isinstance(node, ast.Tuple):
        return any(_is_broad_type(elt) for elt in node.elts)
    if isinstance(node, ast.Name):
        return node.id in BROAD_NAMES
    if isinstance(node, ast.Attribute):
        return (node.attr in BROAD_NAMES and isinstance(node.value, ast.Name)
                and node.value.id == "builtins")
    return False


def _dotted_parts(node: ast.expr) -> List[str]:
    parts: List[str] = []
    while True:
        if isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        elif isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Name):
            parts.append(node.id)
            return parts
        else:
            return parts


def _names_a_logger(part: str) -> bool:
    name = part.lower().lstrip("_")
    return name in ("log", "logging") or "logger" in name or "notifier" in name or "ipc" in name


def _is_report_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        if func.id == "print":
            return any(kw.arg == "file" and "stderr" in _dotted_parts(kw.value)
                       for kw in call.keywords)
        name = func.id.lower().lstrip("_")
        return name == "log" or name.startswith("log_")
    if not isinstance(func, ast.Attribute):
        return False
    owner = _dotted_parts(func.value)
    if func.attr == "warn" and owner == ["warnings"]:
        return True
    if func.attr in ("print_exc", "print_exception") and owner == ["traceback"]:
        return True
    return func.attr in LOG_METHODS and any(_names_a_logger(part) for part in owner)


def _walk_body(statements: Iterable[ast.stmt]) -> Iterator[ast.AST]:
    stack: List[ast.AST] = [node for node in statements if not isinstance(node, NESTED_SCOPES)]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(child for child in ast.iter_child_nodes(node)
                     if not isinstance(child, NESTED_SCOPES))


def handler_swallows(handler: ast.ExceptHandler) -> bool:
    if not _is_broad_type(handler.type):
        return False
    for node in _walk_body(handler.body):
        if isinstance(node, ast.Raise):
            return False
        if isinstance(node, ast.Call) and _is_report_call(node):
            return False
        if (handler.name and isinstance(node, ast.Name) and node.id == handler.name
                and isinstance(node.ctx, ast.Load)):
            return False
    return True


def scan_source(source: str, path: str = "<string>") -> List[Finding]:
    tree = ast.parse(source)
    return [Finding(path, node.lineno) for node in ast.walk(tree)
            if isinstance(node, ast.ExceptHandler) and handler_swallows(node)]


def scan_repository(root: Path = ROOT) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for file in source_files(root, SCAN_ROOTS, (".py",)):
        path = relative(file, root)
        findings = scan_source(read_source(file, root), path)
        if findings:
            counts[path] = len(findings)
    return counts


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    actual = scan_repository()
    if "--list" in argv:
        print_listing(actual, "swallowed error(s)")
        return 0
    return enforce(actual, Ratchet(
        label="Swallowed errors",
        noun="swallowed error(s)",
        remedy="Log it, re-raise it, or catch the precise exception.",
        command="python scripts/audits/audit_swallowed_errors.py",
        baseline=BASELINE,
    ), update="--update-baseline" in argv)


if __name__ == "__main__":
    raise SystemExit(main())
