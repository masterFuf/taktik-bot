"""The catalogues of why a run ends (`contract/stop_reasons.py`) are the values the bot emits.

Each catalogue is held to the code that produces its values, read from the source: a value the bot
starts emitting and the catalogue does not list, or a listed value nothing emits any more, is red.
And every field of a line that says why a run ended refers to a catalogue, not to a free string.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable, Set

from taktik.core.app.contract import TOOL_CONTRACTS, WORKFLOW_CONTRACTS
from taktik.core.app.contract.schema import OneOf, nested_fields
from taktik.core.app.contract.stop_reasons import (
    CATALOGUES,
    INSTAGRAM_SCRAPING_COMPLETION_REASON,
    INSTAGRAM_STOP_REASON_CODE,
    RUN_HALT_CODE,
    TIKTOK_COMPLETION_REASON,
)

ROOT = Path(__file__).resolve().parents[4]

#: The fields of a line that say why a run ended.
REASON_FIELDS = {"completion_reason", "completionReason", "stop_reason", "stopReason", "reason_code"}


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


def _reason_target(node) -> bool:
    if isinstance(node, ast.Name):
        return node.id in ("completion_reason", "stop_reason")
    if isinstance(node, ast.Attribute):
        return node.attr in ("completion_reason", "stop_reason")
    if isinstance(node, ast.Subscript):
        return _string(node.slice) in ("completion_reason", "stop_reason")
    return False


def _tiktok_reasons(paths: Iterable[Path]) -> Set[str]:
    """Every literal a TikTok workflow or bridge sets as a run's reason.

    Assigned to `completion_reason` / `stop_reason` (a name, an attribute, a key), passed under
    that keyword or dict key, returned by `_check_limits_reached`, or held by a module constant
    named `STOP_*` / `ACTION_BLOCKED` (what `stop_reason` is set from).
    """
    found: Set[str] = set()
    for path in paths:
        tree = _tree(path)
        found |= _module_constants(path, lambda name: name.startswith("STOP_") or name == "ACTION_BLOCKED")
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(_reason_target(t) for t in node.targets):
                found.add(_string(node.value))
            elif isinstance(node, ast.keyword) and node.arg in ("completion_reason", "stop_reason"):
                found.add(_string(node.value))
            elif isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if _string(key) in ("completion_reason", "stop_reason"):
                        found.add(_string(value))
            elif isinstance(node, ast.FunctionDef) and node.name == "_check_limits_reached":
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
