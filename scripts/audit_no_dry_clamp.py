"""Audit runtime code for random draws clamped onto their bounds ("dry clamps").

The rule: a random value that falls outside its bounds is DRAWN AGAIN, never pushed onto the
bound. `min(max(gauss(...), lo), hi)` turns every out-of-range draw into exactly `lo` or `hi`, so
the distribution grows a spike on its edges -- taps glued to the rim of their target, durations
worth exactly the minimum. A touch heatmap or a timing histogram shows it at a glance. The shared
primitive is `taktik.core.shared.behavior.sampling.sample_within` (rejection with a bounded number
of tries and a uniform fallback).

What is flagged: a `min(...)` / `max(...)` with two or more arguments, or a `clip(...)` /
`.clip(...)`, where one argument is a RANDOM value -- a call to the `random` module or to an RNG
object (`rng.gauss`, `self._rng.uniform`, ...), a `sample_*` helper, or a local name assigned from
one of those in the same function. A nested `min(max(...))` is reported once. The same clamp
spelled out is flagged too: `if x < lo: x = lo`, and `x if x > lo else lo`, on a random `x`
(a `while` that draws `x` again is a redraw, and is left alone).

What is not flagged: clamps of parameters and of deterministic values (a point kept on screen after
a deterministic computation, a ratio derived from the config). The analysis is per function and
does not follow calls, so a helper that clamps its argument is only seen where the draw happens.

Legitimate clamps of random values exist -- a hard ceiling configured by the user, a geometric
limit the value may not cross -- and are listed in `ALLOWED` with the reason. An entry is keyed by
file, enclosing function and the clamp's source text, so moving code around does not break it,
but rewriting the clamp does (on purpose: the reason must be read again).

Run: ``python scripts/audit_no_dry_clamp.py`` (``--json`` for machine output, ``--show-allowed``
to list the accepted clamps).
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    ROOT / "taktik" / "core",
    ROOT / "bridges",
)
EXCLUDED_PARTS = ("__pycache__", "/tests/", "\\tests\\", "test_")

# Methods of `random.Random` / numpy generators that return a random value.
RANDOM_METHODS = {
    "random", "uniform", "gauss", "normalvariate", "lognormvariate", "triangular",
    "randint", "randrange", "choice", "choices", "sample", "betavariate", "expovariate",
    "gammavariate", "paretovariate", "weibullvariate", "vonmisesvariate",
    "normal", "lognormal", "integers", "exponential",
}
# Receivers that are an RNG: the `random` module, `rng`, `r`, `self._rng`, `np.random`, ...
RNG_RECEIVER_HINTS = ("random", "rng", "rand")
RNG_RECEIVER_NAMES = {"r"}
SAFE_PRIMITIVE = "sample_within"
# Builtins whose result does not carry the randomness of their argument.
DETERMINISTIC_OF_RANDOM = {"len", "isinstance", "callable", "bool", "type"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    function: str
    source: str

    @property
    def key(self) -> Tuple[str, str, str]:
        return (self.path, self.function, self.source)

    def render(self) -> str:
        return (f"{self.path}:{self.line}: in {self.function}(): {self.source} "
                "-- a random draw is clamped onto its bound; draw again instead "
                "(taktik.core.shared.behavior.sampling.sample_within)")


# (path, function, clamp source) -> why this clamp of a random value is legitimate.
ALLOWED: Dict[Tuple[str, str, str], str] = {
    # --- geometry: a limit the value may not cross, whatever was drawn ---------------------
    ("taktik/core/shared/behavior/gesture_primitives.py", "_touch_move_path",
     "min(total, rng.uniform(0.032, 0.045) * screen_h)"):
        "Geometry: the touch-slop exit point cannot lie beyond the end of the path. It only "
        "binds on paths shorter than ~0.045h, which are not scrolls.",
    ("taktik/core/social_media/instagram/actions/business/workflows/common/private_streak_policy.py",
     "flings_for_jump", "min(jittered, reachable)"):
        "Functional ceiling: flings past the bottom of the list only land at the bottom. It "
        "binds on short lists only, where the gesture count is set by the list, not drawn.",
    ("taktik/core/social_media/instagram/actions/business/workflows/common/private_streak_policy.py",
     "flings_for_jump", "max(1, int(round(planned * random.uniform(0.75, 1.25))))"):
        "Guard that never binds: planned >= base_flings >= 1, so the jittered value is at "
        "least 0.75 and rounds to 1 or more.",
    # --- hard limits of the product -----------------------------------------------------------
    ("taktik/core/shared/behavior/interaction_plan.py", "sample_story_like_count",
     "max(0, min(count, cap, n))"):
        "User hard ceiling (max story likes per profile) and physical ceiling (slides in the "
        "story). The product promises 'at most N': landing on N is the contract.",
    ("taktik/core/social_media/instagram/actions/core/base_business/interaction_engine.py",
     "_view_stories_on_current_profile",
     "max(1, sample_story_like_count(watchable, max_story_likes))"):
        "Product floor: when the story-like intent fired, at least one watched slide is liked "
        "(a short story would otherwise be watched and never liked).",
    # --- functional safety caps -------------------------------------------------------------
    ("taktik/core/shared/behavior/dwell.py", "story_dwell",
     "min(max(0.0, float(seconds)), random.uniform(*STORY_AUTOPLAY_SAFE_CAP_S))"):
        "Functional cap below the story auto-advance (a longer dwell skips a slide). The cap is "
        "itself drawn in 3.7-4.4 s, so there is no single value on the trace; the 40-column "
        "histogram shows no peak.",
}


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _is_rng_receiver(node: ast.AST) -> bool:
    text = _dotted(node).lower()
    if not text:
        return False
    last = text.rsplit(".", 1)[-1]
    return last in RNG_RECEIVER_NAMES or any(hint in last for hint in RNG_RECEIVER_HINTS)


def _is_random_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        if func.attr in RANDOM_METHODS and _is_rng_receiver(func.value):
            return True
        name = func.attr
    elif isinstance(func, ast.Name):
        name = func.id
    else:
        return False
    return name.startswith("sample_") or name.startswith("_sample_")


def _is_random_expr(node: ast.AST, tainted: Set[str]) -> bool:
    stack = [node]
    while stack:
        sub = stack.pop()
        if _is_random_call(sub):
            return True
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load) and sub.id in tainted:
            return True
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                and sub.func.id in DETERMINISTIC_OF_RANDOM):
            continue                      # `len(path)` of a sampled path is a count, not a draw
        stack.extend(ast.iter_child_nodes(sub))
    return False


def _target_names(target: ast.AST) -> Iterable[str]:
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            yield from _target_names(elt)
    elif isinstance(target, ast.Starred):
        yield from _target_names(target.value)


def _own_nodes(scope: ast.AST) -> Iterable[ast.AST]:
    """Nodes of `scope` without descending into nested functions or classes."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _tainted_names(scope: ast.AST) -> Set[str]:
    """Local names assigned from a random value, to a fixpoint (flow-insensitive)."""
    assigns: List[Tuple[List[str], ast.AST]] = []
    for node in _own_nodes(scope):
        if isinstance(node, ast.Assign):
            names = [n for t in node.targets for n in _target_names(t)]
            assigns.append((names, node.value))
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)) and node.value is not None:
            assigns.append((list(_target_names(node.target)), node.value))
        elif isinstance(node, ast.NamedExpr):
            assigns.append((list(_target_names(node.target)), node.value))
    tainted: Set[str] = set()
    changed = True
    while changed:
        changed = False
        for names, value in assigns:
            if any(n not in tainted for n in names) and _is_random_expr(value, tainted):
                tainted.update(names)
                changed = True
    return tainted


def _is_clamp_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id in ("min", "max"):
        return len(node.args) >= 2 and not any(isinstance(a, ast.Starred) for a in node.args)
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    return name == "clip"


def _clamp_operands(node: ast.Call) -> List[ast.AST]:
    operands = list(node.args)
    if isinstance(node.func, ast.Attribute) and node.func.attr == "clip":
        if not _dotted(node.func.value).endswith(("np", "numpy")):
            operands.append(node.func.value)    # `x.clip(lo, hi)`
    return operands


_ORDER_OPS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)


def _compared_draw(test: ast.AST, tainted: Set[str]) -> str:
    """The random local compared with a limit in `test` (`x < lo`, `hi <= x`), or ''."""
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1
            and isinstance(test.ops[0], _ORDER_OPS)):
        return ""
    for side in (test.left, test.comparators[0]):
        if isinstance(side, ast.Name) and side.id in tainted:
            return side.id
    return ""


def _spelled_out_clamp(node: ast.AST, tainted: Set[str]) -> str:
    """`if x < lo: x = lo` or `x if x > lo else lo` on a random `x`, as source; '' otherwise."""
    if isinstance(node, ast.If):
        name = _compared_draw(node.test, tainted)
        for stmt in node.body if name else ():
            if (isinstance(stmt, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == name for t in stmt.targets)
                    and not _is_random_expr(stmt.value, tainted)):
                return f"if {ast.unparse(node.test)}: {ast.unparse(stmt)}"
    elif isinstance(node, ast.IfExp):
        name = _compared_draw(node.test, tainted)
        branches = (node.body, node.orelse)
        if (name and any(isinstance(b, ast.Name) and b.id == name for b in branches)
                and any(not _is_random_expr(b, tainted) for b in branches)):
            return ast.unparse(node)
    return ""


def _sample_within_limits(scope: ast.AST) -> Iterable[ast.AST]:
    """The `lo` / `hi` expressions of `sample_within(...)` calls: a min/max there computes a
    limit for the redraw (e.g. the tighter of two caps), it does not clamp a draw."""
    for node in _own_nodes(scope):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name != SAFE_PRIMITIVE:
            continue
        yield from node.args[1:3]
        yield from (kw.value for kw in node.keywords if kw.arg in ("lo", "hi"))


def _scopes(tree: ast.Module) -> Iterable[Tuple[str, ast.AST]]:
    yield "<module>", tree

    def visit(node: ast.AST, prefix: str) -> Iterable[Tuple[str, ast.AST]]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield child.name, child
                yield from visit(child, f"{prefix}{child.name}.")
            elif isinstance(child, ast.ClassDef):
                yield from visit(child, f"{prefix}{child.name}.")
            else:
                yield from visit(child, prefix)

    yield from visit(tree, "")


def _scan_file(path: Path) -> List[Finding]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return scan_source(source, str(path.relative_to(ROOT)).replace("\\", "/"))


def scan_source(source: str, rel: str = "<source>") -> List[Finding]:
    """Dry clamps in one module's source, allowed or not."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    findings: List[Finding] = []
    for name, scope in _scopes(tree):
        tainted = _tainted_names(scope)
        clamps = [
            node for node in _own_nodes(scope)
            if _is_clamp_call(node)
            and any(_is_random_expr(op, tainted) for op in _clamp_operands(node))
        ]
        nested: Set[int] = set()
        for clamp in clamps:
            for sub in ast.walk(clamp):
                if sub is not clamp:
                    nested.add(id(sub))
        for limit in _sample_within_limits(scope):
            nested.update(id(sub) for sub in ast.walk(limit))
        for clamp in clamps:
            if id(clamp) in nested:
                continue
            findings.append(Finding(rel, clamp.lineno, name, ast.unparse(clamp)))
        for node in _own_nodes(scope):
            text = _spelled_out_clamp(node, tainted)
            if text:
                findings.append(Finding(rel, node.lineno, name, text))
    return findings


def collect() -> List[Finding]:
    findings: List[Finding] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if any(part in str(path) for part in EXCLUDED_PARTS):
                continue
            findings.extend(_scan_file(path))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    parser.add_argument("--show-allowed", action="store_true", help="list the accepted clamps")
    args = parser.parse_args()

    all_findings = collect()
    blocking = [f for f in all_findings if f.key not in ALLOWED]
    allowed = [f for f in all_findings if f.key in ALLOWED]
    seen = {f.key for f in all_findings}
    stale = [key for key in ALLOWED if key not in seen]

    if args.json:
        print(json.dumps({
            "findings": [f.__dict__ for f in blocking],
            "allowed": [dict(f.__dict__, reason=ALLOWED[f.key]) for f in allowed],
            "stale_allowlist": [list(key) for key in stale],
        }, indent=2))
    else:
        for finding in blocking:
            print(finding.render())
        if args.show_allowed:
            for finding in allowed:
                print(f"[allowed] {finding.path}:{finding.line}: in {finding.function}(): "
                      f"{finding.source}\n          {ALLOWED[finding.key]}")
        for key in stale:
            print(f"[stale allowlist entry] {key[0]} :: {key[1]} :: {key[2]}")
        if blocking or stale:
            print(f"\nDry clamp audit FAILED ({len(blocking)} finding(s), "
                  f"{len(stale)} stale allowlist entr{'y' if len(stale) == 1 else 'ies'})")
        else:
            print(f"Dry clamp audit OK (0 findings, {len(allowed)} accepted clamp(s))")
    return 1 if (blocking or stale) else 0


if __name__ == "__main__":
    raise SystemExit(main())
