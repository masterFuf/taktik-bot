"""Ratchet gate: the number of type errors per file, as pyright reads them, may only go down.

Typed Python reads like TypeScript: a signature says what goes in and out, and a misuse is seen
before the run, not on the phone. The engine is not typed yet; this gate does not ask to type it
all at once, it freezes today's errors file by file and refuses any new one.

Configuration: ``pyrightconfig.json`` at the root of the engine, read by editors too (Pylance shows
the same errors): ``taktik``, ``bridges`` and ``scripts``; mode ``standard`` (pyright's default,
which adds to ``basic`` the possibly unbound variable and the incompatible override); Python 3.10,
the oldest version the engine supports; platform Windows, where the desktop app runs it, so that
every machine counts the same. Tests are not checked: their doubles are duck-typed on purpose.

The tool is pyright ``PYRIGHT_VERSION`` exactly: another version counts differently. It is found,
in order, at ``TAKTIK_PYRIGHT`` (a path), in the engine's virtual environment (``.venv``), or on the
PATH. It is never a requirement of the bot. Without it the gate is red and says how to get it (see
``INSTALL``): a gate that passes because its tool is missing guards nothing.

Imports are resolved with the Python that runs the gate (``--pythonpath``), which must have the
engine's requirements. An absolute import that pyright cannot resolve is not counted: it is
reported as an incomplete environment and the gate is red, because a module without types hides
every misuse of it and would lower the counts silently. A relative import that does not resolve is
an error of the code and is counted.

Count: the diagnostics of severity ``error``, per file. Ratchet: ``scripts/ratchet.py``, baseline
``scripts/audit_type_errors_baseline.json``.

Usage:
    python scripts/audit_type_errors.py                    # green / red
    python scripts/audit_type_errors.py --list             # totals, zones, rules, heaviest files
    python scripts/audit_type_errors.py --update-baseline  # record decreases only
    python scripts/audit_type_errors.py --self-test        # pyright on a throwaway tree turns it red
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from ratchet import Ratchet, enforce, print_listing

ROOT = Path(__file__).resolve().parents[1]
CONFIG_NAME = "pyrightconfig.json"
BASELINE = ROOT / "scripts" / "audit_type_errors_baseline.json"
PYRIGHT_VERSION = "1.1.414"
NOUN = "type error(s)"
INSTALL = (f"python -m venv .venv, then .venv/Scripts/python -m pip install pyright=={PYRIGHT_VERSION} "
           "(.venv/bin/python outside Windows), from the root of the engine; or TAKTIK_PYRIGHT=<path to "
           "pyright>. Never in the bot's requirements.")


@dataclass
class Reading:
    """What the gate takes from one pyright report."""

    counts: Dict[str, int] = field(default_factory=dict)
    rules: Dict[str, int] = field(default_factory=dict)
    environment: List[str] = field(default_factory=list)
    analysed: int = 0

    def failures(self) -> List[str]:
        """Findings outside the count: they turn the gate red whatever the baseline says."""
        found = [f"{line}: an absolute import that does not resolve; install the engine's "
                 f"requirements in {sys.executable} (if it still does not resolve, it is missing "
                 f"from requirements.txt)" for line in self.environment]
        if not self.analysed:
            found.append(f"pyright analysed no file: check {CONFIG_NAME} (its include list)")
        return found


def _imported_module(message: str) -> str:
    """`Import "x.y" could not be resolved` -> `x.y`."""
    return message.split('"')[1] if message.count('"') >= 2 else ""


def read_report(report: Mapping, root: Path) -> Reading:
    reading = Reading(analysed=report.get("summary", {}).get("filesAnalyzed", 0))
    counts: Counter = Counter()
    rules: Counter = Counter()
    for diagnostic in report.get("generalDiagnostics", []):
        if diagnostic.get("severity") != "error":
            continue
        path = Path(diagnostic["file"]).relative_to(root).as_posix()
        rule = diagnostic.get("rule", "(syntax)")
        message = diagnostic["message"].split("\n")[0]
        if rule == "reportMissingImports" and not _imported_module(message).startswith("."):
            line = diagnostic["range"]["start"]["line"] + 1
            reading.environment.append(f"{path}:{line} {message}")
            continue
        counts[path] += 1
        rules[rule] += 1
    reading.counts = dict(counts)
    reading.rules = dict(rules)
    return reading


class ToolFailure(Exception):
    """pyright could not run, or did not answer as expected; the message says what it said."""


def find_pyright() -> Optional[str]:
    explicit = os.environ.get("TAKTIK_PYRIGHT")
    if explicit:
        return explicit
    for candidate in (ROOT / ".venv" / "Scripts" / "pyright.exe", ROOT / ".venv" / "bin" / "pyright"):
        if candidate.exists():
            return str(candidate)
    return shutil.which("pyright")


def _run(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(list(command), cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
    except OSError as exc:
        raise ToolFailure(f"{command[0]} could not be started: {exc}") from exc


def pyright_version(executable: str) -> str:
    run = _run([executable, "--version"], ROOT)
    words = run.stdout.split()
    if run.returncode != 0 or len(words) < 2:
        raise ToolFailure(f"{executable} --version answered: {(run.stdout + run.stderr).strip()[:300]}")
    return words[-1]


def run_pyright(executable: str, root: Path) -> Reading:
    run = _run([executable, "--outputjson", "--project", str(root / CONFIG_NAME),
                "--pythonpath", sys.executable], root)
    # 0: no error, 1: errors found; anything else is pyright failing (configuration, command line).
    if run.returncode not in (0, 1):
        raise ToolFailure(f"pyright exited with {run.returncode}: {(run.stderr or run.stdout).strip()[:500]}")
    try:
        report = json.loads(run.stdout)
    except json.JSONDecodeError as exc:
        raise ToolFailure(f"pyright did not answer JSON ({exc}): {run.stdout[:300]}") from exc
    return read_report(report, root)


def _ratchet(baseline: Path) -> Ratchet:
    return Ratchet(
        label="Type errors",
        noun=NOUN,
        remedy="Fix the type error (declare the attribute, the Optional, the return type) instead of adding one.",
        command="python scripts/audit_type_errors.py",
        baseline=baseline,
    )


def measure(root: Path = ROOT) -> Reading:
    """pyright on `root`, raising ToolFailure when it is missing, of another version, or fails."""
    executable = find_pyright()
    if executable is None:
        raise ToolFailure(f"pyright not found. {INSTALL}")
    version = pyright_version(executable)
    if version != PYRIGHT_VERSION:
        raise ToolFailure(f"pyright {version} found, the gate counts with {PYRIGHT_VERSION}. {INSTALL}")
    return run_pyright(executable, root)


def print_rules(rules: Mapping[str, int]) -> None:
    print("\nBy rule:")
    for rule, count in sorted(rules.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {count:5d}  {rule}")


def self_test_tree() -> Dict[str, str]:
    """A throwaway package: one clean file, two errors in one file, one relative import that does not resolve."""
    return {
        "pkg/__init__.py": "",
        "pkg/clean.py": "def double(value: int) -> int:\n    return value * 2\n",
        "pkg/wrong.py": ("from pkg.clean import double\n\n"
                         "count: int = 'three'\n"
                         "twice: str = double(2)\n"),
        "pkg/relative.py": "from .missing import thing\n",
    }


def self_test() -> int:
    """pyright, with the engine's own configuration, on a throwaway tree: each judgement as expected."""
    config = json.loads((ROOT / CONFIG_NAME).read_text(encoding="utf-8"))
    missed: List[str] = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder).resolve()
        (root / CONFIG_NAME).write_text(json.dumps({**config, "include": ["pkg"]}), encoding="utf-8")
        for path, text in self_test_tree().items():
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text(text, encoding="utf-8")
        reading = measure(root)
        expected = {"pkg/wrong.py": 2, "pkg/relative.py": 1}
        if reading.counts != expected or reading.failures():
            missed.append(f"pyright read {reading.counts} {reading.failures()}, expected {expected}")
        judgements = {
            "the baseline up to date": (expected, 0),
            "a new error in a file": ({**expected, "pkg/wrong.py": 1}, 1),
            "a new file with an error": ({"pkg/wrong.py": 2}, 1),
            "a decrease not recorded": ({**expected, "pkg/wrong.py": 3}, 1),
        }
        for name, (baseline, verdict) in judgements.items():
            (root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                judged = enforce(reading.counts, _ratchet(root / "baseline.json"))
            if judged != verdict:
                missed.append(f"{name}: expected {'red' if verdict else 'green'}")
        (root / "pkg" / "environment.py").write_text("import a_module_nobody_installed\n", encoding="utf-8")
        with_environment = measure(root)
        if not any("a_module_nobody_installed" in line for line in with_environment.failures()):
            missed.append("an absolute import that does not resolve: expected red, not reported")
        if with_environment.counts != expected:
            missed.append(f"an absolute import that does not resolve was counted: {with_environment.counts}")
    for line in missed:
        print(f"Self-test FAILED, {line}")
    if missed:
        return 1
    print(f"Type errors self-test OK (pyright {PYRIGHT_VERSION} on a throwaway tree, "
          f"{len(judgements) + 1} judgements as expected)")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        if "--self-test" in argv:
            return self_test()
        reading = measure(ROOT)
    except ToolFailure as exc:
        print(f"FAIL: {exc}")
        return 1
    if "--list" in argv:
        print_listing(reading.counts, NOUN)
        print_rules(reading.rules)
        return 0
    return enforce(reading.counts, _ratchet(BASELINE), update="--update-baseline" in argv,
                   other_failures=reading.failures())


if __name__ == "__main__":
    raise SystemExit(main())
