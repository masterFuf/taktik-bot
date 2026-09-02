"""Audit: no bridge wires a profile-visiting workflow's callbacks by hand.

Three TikTok bridges walk profiles the same way -- Followers, Target Profiles, Post URL -- and
report the same four things. Two of them wired those four themselves, in near-identical copies,
and the copies drifted: Target Profiles never learned about the profile callback.

The failure was silent by construction. `_send_profile` returns immediately when nobody is
listening, so the workflow captured @yam_7770's avatar on the device, logged it as captured
(256x256, 14 Ko) and dropped it. The card kept showing a letter. The AI classification, wired
elsewhere, arrived fine -- so the run read as a success.

The rule this enforces: wiring goes through `wire_workflow_callbacks`, so a callback added to the
family reaches every bridge at once instead of the one whose file someone happened to open.

Deliberately narrow: only a `set_on_*_callback(` CALL on something is flagged, and only inside
`bridges/`, and only outside the one module allowed to make them. A workflow DEFINING a setter, a
test wiring a fake, or a comment naming one are all fine.

Run: ``python scripts/audit_workflow_callbacks.py`` (add ``--json`` for machine output).
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
#: The profile-visiting bridges. Video-based families (For You, Search) and the scraping
#: workflow live elsewhere and wire their own things -- a search run reports videos, not
#: visited profiles, and has no avatar to lose.
SCAN_ROOT = ROOT / "bridges" / "tiktok" / "workflows" / "automation"

#: The one module allowed to wire them -- it is where the shared wiring lives.
WIRING_MODULE = (
    ROOT / "bridges" / "tiktok" / "workflows" / "automation" / "runtime" / "workflow_callbacks.py"
)

#: Setters that belong to the profile-visiting family. `set_on_stats_callback` is NOT here: the
#: stats payload is genuinely per-bridge and is passed into the shared wiring as an argument.
SETTERS = {"set_on_action_callback", "set_on_profile_callback", "set_on_pause_callback"}

#: Wires a VIDEO workflow, which happens to live under the same folder. Search and hashtag runs
#: report `video_info` and never visit a profile, so they have no avatar to drop and nothing to
#: gain from the shared wiring. Listed by name rather than guessed, so the day it starts visiting
#: profiles this line has to be revisited on purpose.
ALLOWED = {"runtime/search_callbacks.py"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    setter: str
    snippet: str


def _sources() -> Iterable[Path]:
    if not SCAN_ROOT.exists():
        return
    for path in sorted(SCAN_ROOT.rglob("*.py")):
        if path.resolve() == WIRING_MODULE.resolve():
            continue
        if str(path.relative_to(SCAN_ROOT)).replace("\\", "/") in ALLOWED:
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
        setter = getattr(node.func, "attr", None)
        if setter not in SETTERS:
            continue
        snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        found.append(
            Finding(str(path.relative_to(ROOT)).replace("\\", "/"), node.lineno, setter, snippet)
        )
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
        print("Workflow callback audit OK (0 findings)")
        return 0

    print(f"Workflow callback audit: {len(findings)} hand-wired callback(s)")
    print("Use `wire_workflow_callbacks(workflow, on_stats=...)` -- a hand-wired bridge drifts.")
    for finding in findings:
        print(f"  {finding.path}:{finding.line}  {finding.snippet}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
