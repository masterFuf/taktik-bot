"""Audit: nobody builds a second `LocalDatabaseService`.

The service is a singleton behind `get_local_database()`, and its constructor is not cheap: it
runs the WHOLE migration suite and rebuilds the SQLAlchemy engine. 56 ms measured on this machine,
and -- the part that matters more -- a write lock on a database file shared with the Electron app
and its renderer.

Four call sites had been bypassing the accessor. Two of them sat on the comment path, so every
comment the bot posted re-initialised the database twice: once for `record`, once for
`attach_post_url`. It showed up in a real run log as the entire migration pass unrolling between
"Comment posted successfully" and the next navigation -- a hundred comments, eleven seconds of
migrations, and a lock taken a hundred times for nothing.

Deliberately narrow, so it stays green and can be believed: only a direct `LocalDatabaseService(`
CALL is flagged, and only outside the accessor's own module. Importing the class for a type hint,
subclassing it, or naming it in a comment are all fine.

Run: ``python scripts/audit_database_singleton.py`` (add ``--json`` for machine output).
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (ROOT / "taktik", ROOT / "bridges")

#: The one module allowed to build it -- it is where the singleton lives.
ACCESSOR_MODULE = ROOT / "taktik" / "core" / "database" / "local" / "service.py"

CLASS_NAME = "LocalDatabaseService"


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    snippet: str


def _sources() -> Iterable[Path]:
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if path.resolve() == ACCESSOR_MODULE.resolve():
                continue
            yield path


def _findings_in(path: Path) -> List[Finding]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return []

    lines = source.splitlines()
    found: List[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name != CLASS_NAME:
            continue
        snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        found.append(Finding(str(path.relative_to(ROOT)).replace("\\", "/"), node.lineno, snippet))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    findings = [f for path in _sources() for f in _findings_in(path)]

    if args.json:
        print(json.dumps([f.__dict__ for f in findings], indent=2))
        return 1 if findings else 0

    if not findings:
        print("Database singleton audit OK (0 findings)")
        return 0

    print(f"Database singleton audit: {len(findings)} direct construction(s) of {CLASS_NAME}")
    print("Use `get_local_database()` instead -- the constructor re-runs every migration.")
    for finding in findings:
        print(f"  {finding.path}:{finding.line}  {finding.snippet}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
