"""Ratchet gate: the adb calls made outside the door to the phone's shell may only go down.

`adb shell` joins its arguments with spaces and the phone's shell splits the line again: what the
phone runs is not what the caller wrote as soon as a word holds a space, a quote, a `$`, an `&`.
The door, `taktik/core/shared/device/adb.py`, applies one rule (a list: each word reaches the phone
whole; a string: the line as written). This gate counts, per file, the two ways around it (read on
the ``ast``, never on the text):

* ARGV: a list or a tuple whose first item is the string ``"adb"`` (or ``"adb.exe"``): adb launched
  by hand, its arguments joined by adb without quoting (``["adb", "-s", serial, "shell", "am",
  "start", "-d", url]`` cut a TikTok link at its ``&``).
* INTERPOLATED LINE: a line for the phone's shell built by interpolation in the call itself, the
  command of ``run_adb_shell(...)``, ``run_adb_shell_process(...)``, ``_run_adb_shell(...)`` or of a
  device's ``.shell(...)`` / ``.shell2(...)`` written as an f-string with a value, a ``+`` or ``%``
  of strings, or a ``.format(...)`` (``f'input text "{password}"'`` expanded the ``$`` of a
  password). A list of words is the safe form; a constant line is what it says.

The door itself is not scanned. The rule, the door and the app's twin gate (`npm run adb:calls`,
which counts the app's adb launches with the same ratchet) are described in
`docs/governance/anti-derive.md`.

Ratchet (``scripts/audits/ratchet.py``, shared by the counting gates):
``scripts/audits/audit_adb_calls_baseline.json`` maps each file to its count. Red when a file exceeds
its count, when a file absent from the baseline has one, and when a count in the baseline is higher
than reality (lower the baseline: the ratchet never goes back up).

Usage:
    python scripts/audits/audit_adb_calls.py                    # green / red
    python scripts/audits/audit_adb_calls.py --list             # each call, by file
    python scripts/audits/audit_adb_calls.py --update-baseline  # record decreases only
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ratchet import Ratchet, enforce, read_source, relative, source_files

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = ("taktik", "bridges", "scripts")
BASELINE = ROOT / "scripts" / "audits" / "audit_adb_calls_baseline.json"
DOOR = "taktik/core/shared/device/adb.py"

ADB_NAMES = frozenset({"adb", "adb.exe"})
#: Calls whose SECOND argument is the command for the phone's shell (the first is the serial).
DOOR_CALLS = frozenset({"run_adb_shell", "run_adb_shell_process", "_run_adb_shell"})
#: A device's own shell (uiautomator2, adbutils): the FIRST argument is the command.
DEVICE_SHELL_CALLS = frozenset({"shell", "shell2"})

ARGV = "argv"
INTERPOLATED = "interpolated line"


@dataclass(frozen=True)
class Finding:
    line: int
    kind: str


def _is_adb_argv(node: ast.List | ast.Tuple) -> bool:
    if not node.elts:
        return False
    first = node.elts[0]
    return isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value in ADB_NAMES


def _called_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def _command_argument(call: ast.Call) -> Optional[ast.expr]:
    name = _called_name(call)
    for keyword in call.keywords:
        if keyword.arg in ("command", "cmdargs"):
            return keyword.value
    if name in DOOR_CALLS:
        return call.args[1] if len(call.args) > 1 else None
    if name in DEVICE_SHELL_CALLS and isinstance(call.func, ast.Attribute):
        return call.args[0] if call.args else None
    return None


def _is_interpolated(node: ast.expr) -> bool:
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(part, ast.FormattedValue) for part in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return isinstance(node.func.value, (ast.Constant, ast.JoinedStr))
    return False


def scan_source(source: str, path: str = "<source>") -> List[Finding]:
    tree = ast.parse(source, filename=path)
    findings: List[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)) and _is_adb_argv(node):
            findings.append(Finding(node.lineno, ARGV))
        elif isinstance(node, ast.Call):
            command = _command_argument(node)
            if command is not None and _is_interpolated(command):
                findings.append(Finding(node.lineno, INTERPOLATED))
    return sorted(findings, key=lambda finding: finding.line)


def scan_repository(root: Path = ROOT) -> Dict[str, List[Finding]]:
    found: Dict[str, List[Finding]] = {}
    for file in source_files(root, SCAN_ROOTS, (".py",)):
        path = relative(file, root)
        if path == DOOR:
            continue
        findings = scan_source(read_source(file, root), path)
        if findings:
            found[path] = findings
    return found


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    found = scan_repository()
    if "--list" in argv:
        for path, findings in sorted(found.items()):
            print(f"{len(findings):4d}  {path}")
            for finding in findings:
                print(f"        line {finding.line}: {finding.kind}")
        print(f"\n{sum(len(f) for f in found.values())} adb call(s) outside the door in {len(found)} file(s).")
        return 0
    return enforce({path: len(findings) for path, findings in found.items()}, Ratchet(
        label="Adb calls outside the door",
        noun="adb call(s) outside the door",
        remedy=("Go through taktik/core/shared/device/adb.py with a LIST of words "
                "(run_adb_shell_process(serial, ['am', 'start', '-d', url])), never a line built by interpolation."),
        command="python scripts/audits/audit_adb_calls.py",
        baseline=BASELINE,
    ), update="--update-baseline" in argv)


if __name__ == "__main__":
    raise SystemExit(main())
