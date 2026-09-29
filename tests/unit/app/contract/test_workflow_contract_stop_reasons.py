"""The catalogues of why a run ends (`contract/stop_reasons.py`) are the values the bot emits.

Each catalogue is held to the code that produces its values, read from the source: a value the bot
starts emitting and the catalogue does not list, or a listed value nothing emits any more, is red.
And every field of a line that says why a run ended refers to a catalogue, not to a free string.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable, Set

from taktik.core.contract import TOOL_CONTRACTS, WORKFLOW_CONTRACTS
from taktik.core.contract.schema import OneOf, nested_fields
from taktik.core.contract.stop_reasons import (
    CATALOGUES,
    INSTAGRAM_SCRAPING_COMPLETION_REASON,
    INSTAGRAM_STOP_REASON_CODE,
    INSTAGRAM_SUGGESTIONS_VISIT_STOP_REASON,
    RUN_HALT_CODE,
    TIKTOK_COMPLETION_REASON,
)

ROOT = Path(__file__).resolve().parents[4]

#: The fields of a line that say why a run (or a pass of it) ended.
REASON_FIELDS = {"completion_reason", "completionReason", "stop_reason", "stopReason", "reason_code"}

#: The names a workflow sets a run's reason under.
REASON_NAMES = ("completion_reason", "stop_reason")


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8-sig"))


def _string(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _module_constants(path: Path, accept=lambda name: name.isupper()) -> Set[str]:
    """The module-level string constants whose name `accept` takes."""
    return {
        _string(node.value)
        for node in _tree(path).body
        if isinstance(node, ast.Assign) and _string(node.value) is not None
        for target in node.targets
        if isinstance(target, ast.Name) and accept(target.id)
    }


def test_the_halt_codes_are_the_latch_constants():
    halt = ROOT / "taktik" / "core" / "shared" / "diagnostics" / "run_halt.py"
    assert set(RUN_HALT_CODE.values) == _module_constants(halt)


def test_the_instagram_codes_are_the_catalogue_factories():
    catalogue = ROOT / "taktik" / "core" / "social_media" / "instagram" / "workflows" / "management" / "session" / "stop_reasons.py"
    built = {
        _string(node.args[0])
        for node in ast.walk(_tree(catalogue))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_reason" and node.args
    }
    assert None not in built, "a code built from a variable: the catalogue cannot be read"
    assert set(INSTAGRAM_STOP_REASON_CODE.values) == built


def test_the_instagram_scraping_reasons_are_its_outcome_constants():
    outcome = ROOT / "taktik" / "core" / "social_media" / "instagram" / "workflows" / "scraping" / "outcome.py"
    assert set(INSTAGRAM_SCRAPING_COMPLETION_REASON.values) == _module_constants(outcome)


def _reason_target(node, names: Iterable[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Attribute):
        return node.attr in names
    if isinstance(node, ast.Subscript):
        return _string(node.slice) in names
    return False


def _literals_set_in(roots: Iterable[ast.AST], names: Iterable[str]) -> Set[str]:
    """Every literal the code under `roots` sets under one of `names`.

    Assigned to it (a name, an attribute, a key), or passed under that keyword or dict key.
    """
    names = tuple(names)
    found: Set[str] = set()
    for root in roots:
        for node in ast.walk(root):
            if isinstance(node, ast.Assign) and any(_reason_target(t, names) for t in node.targets):
                found.add(_string(node.value))
            elif isinstance(node, ast.keyword) and node.arg in names:
                found.add(_string(node.value))
            elif isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if _string(key) in names:
                        found.add(_string(value))
    return {value for value in found if value}


def _literals_set_as(paths: Iterable[Path], names: Iterable[str] = REASON_NAMES) -> Set[str]:
    """Every literal the code of `paths` sets under one of `names` (`_literals_set_in`)."""
    return _literals_set_in((_tree(path) for path in paths), names)


def _read_from(value, variable: str, names: Iterable[str]) -> bool:
    """`variable["name"]`, for one of `names`."""
    return (isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name) and value.value.id == variable
            and _string(value.slice) in names)


def _steps_a_reason_is_taken_from(root: ast.AST, names: Iterable[str]) -> Set[str]:
    """The methods whose reason a function of `root` takes as its own: `entry = self.step(...)`, then
    a reason set from `entry["..."]` in the same function."""
    names = tuple(names)
    steps: Set[str] = set()
    for function in (node for node in ast.walk(root) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
        called = {
            node.targets[0].id: node.value.func.attr
            for node in ast.walk(function)
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == "self"
        }
        for node in ast.walk(function):
            if isinstance(node, ast.Assign) and any(_reason_target(t, names) for t in node.targets):
                steps |= {step for variable, step in called.items() if _read_from(node.value, variable, names)}
    return steps


def _reasons_set_by_the_steps(paths: Iterable[Path], names: Iterable[str]) -> Set[str]:
    """Every literal set under `names` by the steps the code of `paths` takes its reason from
    (`_steps_a_reason_is_taken_from`), and by theirs in turn. A step is a method of the same host: it
    is looked for in the modules beside the one that calls it (the mixins of that host)."""
    names = tuple(names)
    found: Set[str] = set()
    seen: Set[tuple] = set()
    pending = [(path.parent, step) for path in paths for step in _steps_a_reason_is_taken_from(_tree(path), names)]
    while pending:
        folder, step = pending.pop()
        if (folder, step) in seen:
            continue
        seen.add((folder, step))
        definitions = [
            node
            for module in folder.glob("*.py")
            for node in ast.walk(_tree(module))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == step
        ]
        assert definitions, f"`{step}`, whose reason is taken, is defined nowhere beside its caller in {folder}"
        found |= _literals_set_in(definitions, names)
        pending += [(folder, inner) for definition in definitions
                    for inner in _steps_a_reason_is_taken_from(definition, names)]
    return found


def _tiktok_reasons(paths: Iterable[Path]) -> Set[str]:
    """Every literal a TikTok workflow or bridge sets as a run's reason.

    Set as `completion_reason` / `stop_reason`, returned by `_check_limits_reached`, or held by a
    module constant named `STOP_*` / `ACTION_BLOCKED` (what `stop_reason` is set from).
    """
    paths = list(paths)
    found: Set[str] = _literals_set_as(paths)
    for path in paths:
        found |= _module_constants(path, lambda name: name.startswith("STOP_") or name == "ACTION_BLOCKED")
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.FunctionDef) and node.name == "_check_limits_reached":
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Return):
                        found.add(_string(inner.value))
    return {value for value in found if value}


def test_the_tiktok_reasons_are_what_its_workflows_set():
    paths = [*(ROOT / "taktik" / "core" / "social_media" / "tiktok").rglob("*.py"),
             *(ROOT / "bridges" / "tiktok").rglob("*.py")]
    # The latch's codes reach `completion_reason` / `stop_reason` through `halt["code"]`.
    set_by_code = _tiktok_reasons(paths) | set(RUN_HALT_CODE.values)
    assert set(TIKTOK_COMPLETION_REASON.values) == set_by_code


def test_the_suggestions_visit_reasons_are_what_the_pass_sets():
    instagram = ROOT / "taktik" / "core" / "social_media" / "instagram"
    paths = [
        instagram / "actions" / "business" / "workflows" / "common" / "suggestion_visit.py",
        instagram / "actions" / "business" / "workflows" / "feed" / "suggestions_visit.py",
        instagram / "workflows" / "management" / "notifications" / "suggestions_flow.py",
        instagram / "workflows" / "management" / "notifications" / "commands.py",
    ]
    # A surface that cannot be reached gives its `reach_failure_reason`; the activity screen's
    # is where its descent stopped (`descent_outcome`), whose "reached" never fails the reach.
    names = (*REASON_NAMES, "reach_failure_reason", "descent_outcome")
    # The people screen takes its entry's reason as its own: the step the bulk follow shares.
    set_by_code = _literals_set_as(paths, names) | _reasons_set_by_the_steps(paths, names)
    set_by_code.discard("reached")
    # The latch's codes reach it through `halt.get("code")`.
    assert set(INSTAGRAM_SUGGESTIONS_VISIT_STOP_REASON.values) == set_by_code | set(RUN_HALT_CODE.values)


def test_a_catalogue_is_a_named_closed_set_without_duplicates():
    names = [catalogue.name for catalogue in CATALOGUES]
    assert all(names) and len(names) == len(set(names))
    for catalogue in CATALOGUES:
        assert len(catalogue.values) == len(set(catalogue.values)), catalogue.name


def test_every_reason_a_line_carries_is_a_catalogue():
    owners = [*WORKFLOW_CONTRACTS, *TOOL_CONTRACTS]
    free = []
    for owner in owners:
        for event in owner.events:
            for path, item, _, _ in nested_fields(event.fields):
                if item.key in REASON_FIELDS:
                    spec = item.type
                    if not (isinstance(spec, OneOf) and spec.name in {c.name for c in CATALOGUES}):
                        free.append(f"{getattr(owner, 'workflow_id', owner.name)} `{event.type}`.{'.'.join(path)}")
    assert not free, f"a reason typed as a free string: {sorted(set(free))}"


def test_the_session_stop_carries_a_catalogue_code():
    from taktik.core.social_media.instagram.workflows.management.session import stop_reasons

    fields = stop_reasons.follows_cap(5, 5).event_fields()
    assert fields["reason_code"] in INSTAGRAM_STOP_REASON_CODE.values
    assert stop_reasons.for_halt({"code": "desktop_gone"}).code in INSTAGRAM_STOP_REASON_CODE.values
