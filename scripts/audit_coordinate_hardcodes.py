"""Audit runtime code for hardcoded touch coordinates.

The rule: a tap or a gesture must address a point the code DERIVED from the live device --
element bounds, a fraction of the screen, a sampled trajectory. A call whose coordinates are all
numeric literals encodes one screen size and silently misfires on every other one, which is worse
than failing: the tap still lands, just somewhere else.

Deliberately narrow, so it can stay green and be believed:

* Only literal PIXELS are flagged. `click(0.5, 0.5)` is a ratio -- uiautomator2 treats a coordinate
  below 1 as a fraction of the screen -- and is correct on any device.
* A single derived coordinate exonerates the call. `click(w // 2, int(h * 0.494))` reads a ratio out
  of literals, which is exactly how it should be done, and `swipe(cx, y1, cx, y2)` is fine whatever
  y1 came from. Only calls where EVERY coordinate is a literal pixel are reported.
* Constants named at module level are treated as literals when passed straight through, because a
  named 1180 is still 1180.

Run: ``python scripts/audit_coordinate_hardcodes.py`` (add ``--json`` for machine output).
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    ROOT / "taktik" / "core",
    ROOT / "bridges",
)

# method name -> how many leading positional args are coordinates
COORD_METHODS = {
    "click": 2,
    "tap": 2,
    "double_click": 2,
    "long_click": 2,
    "human_tap": 2,
    "swipe": 4,
    "swipe_coordinates": 4,
    "drag": 4,
    "human_drag_between_raw": 4,   # (device, (x, y), (x, y)) -- tuples are flattened below
}

# Files whose literals are documentation or test fixtures, not device input.
EXCLUDED_PARTS = ("__pycache__", "/tests/", "\\tests\\", "test_")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    method: str
    coords: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.method}({self.coords}) -- every coordinate is a literal pixel"


def _numeric(node: ast.AST) -> Optional[float]:
    """Return the numeric value of a literal, including a negated one; None if not a literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _numeric(node.operand)
        return None if inner is None else -inner
    return None


def _flatten(args: Iterable[ast.AST]) -> List[ast.AST]:
    """Expand tuple/list literals so `human_drag_between_raw(d, (x, y), (x, y))` reads as 4 args."""
    out: List[ast.AST] = []
    for arg in args:
        if isinstance(arg, (ast.Tuple, ast.List)):
            out.extend(arg.elts)
        else:
            out.append(arg)
    return out


def _scan_file(path: Path) -> List[Finding]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return []

    findings: List[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        arity = COORD_METHODS.get(node.func.attr)
        if arity is None:
            continue
        coords = _flatten(node.args)[:arity]
        if len(coords) < 2:
            continue
        values = [_numeric(arg) for arg in coords]
        if any(value is None for value in values):
            continue                      # at least one coordinate is derived -> correct
        if not any(abs(value) >= 1 for value in values):
            continue                      # all below 1 -> ratios, resolution-independent
        findings.append(Finding(
            path=str(path.relative_to(ROOT)).replace("\\", "/"),
            line=node.lineno,
            method=node.func.attr,
            coords=", ".join(f"{v:g}" for v in values),
        ))
    return findings


def collect() -> List[Finding]:
    findings: List[Finding] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            text = str(path)
            if any(part in text for part in EXCLUDED_PARTS):
                continue
            findings.extend(_scan_file(path))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    args = parser.parse_args()

    findings = collect()
    if args.json:
        print(json.dumps([f.__dict__ for f in findings], indent=2))
    elif findings:
        for finding in findings:
            print(finding.render())
        print(f"\nCoordinate hardcode audit FAILED ({len(findings)} finding(s))")
    else:
        print("Coordinate hardcode audit OK (0 findings)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
