"""What every Agent handler reads the same way: `taktik/core/kernel/handler_params.py`.

The merge of a step's params over the executor's payload has one home. A handler that writes the
two lines again (`merged = dict(payload)` then `merged.update(invocation.params)`) is a second way
to do it, and the structural test below names it.

The clone a run starts has one reading too, for Instagram and TikTok alike: `package_name_from_payload`
(`packageName` or `package_name`, spaces dropped, blank: the installed app). Instagram read it in
`startup.py`, the TikTok account flows by a copy, the TikTok publication by its own rule (the first
key that is not None: spaces kept, a blank package taken for a clone, an empty `packageName` hiding
`package_name`). The second structural test names any reading of the field outside its reader.
"""

import ast

import pytest

from taktik.core.kernel.contracts import WorkflowInvocation
from taktik.core.kernel.handler_params import (
    merge_invocation_payload,
    package_name_from_payload,
    text_param,
    value_param,
)
from unit.paths import CORE

HOME = CORE / "taktik" / "core" / "kernel" / "handler_params.py"


def test_step_params_win_over_the_payload_and_the_payload_is_left_alone():
    payload = {"device_id": "phone", "limit": 5}
    invocation = WorkflowInvocation(platform="instagram", workflow_id="instagram.automation.feed", params={"limit": 9})

    merged = merge_invocation_payload(invocation, payload)

    assert merged == {"device_id": "phone", "limit": 9}
    assert payload == {"device_id": "phone", "limit": 5}
    assert merged is not payload


def test_a_step_without_params_gives_a_copy_of_the_payload():
    payload = {"device_id": "phone"}

    merged = merge_invocation_payload(WorkflowInvocation(platform="instagram", workflow_id="x"), payload)

    assert merged == payload and merged is not payload


def test_value_param_reads_the_first_name_that_is_set():
    assert value_param({"a": None, "b": 0, "c": 1}, "a", "b", "c", default=7) == 0
    assert value_param({}, "a", default=7) == 7


def _merges_by_hand(tree: ast.AST) -> list[int]:
    """Lines of `<name>.update(invocation.params)`: the merge written outside its home."""
    lines = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "update"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Attribute)
            and node.args[0].attr == "params"
            and isinstance(node.args[0].value, ast.Name)
            and node.args[0].value.id == "invocation"
        ):
            lines.append(node.lineno)
    return lines


def test_no_handler_merges_the_step_params_by_hand():
    found = []
    for path in sorted((CORE / "taktik").rglob("*.py")):
        if path == HOME:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        found += [f"{path.relative_to(CORE).as_posix()}:{line}" for line in _merges_by_hand(tree)]
    assert not found, (
        "merge the step params with `merge_invocation_payload` (taktik/core/kernel/handler_params.py): "
        + ", ".join(found)
    )


def test_the_structural_check_sees_a_merge_by_hand():
    tree = ast.parse("def handler(invocation, payload):\n    merged = dict(payload)\n    merged.update(invocation.params)\n")
    assert _merges_by_hand(tree) == [3]


def test_text_param_reads_the_first_name_with_text_spaces_dropped():
    assert text_param({"a": None, "b": "  ", "c": " x "}, "a", "b", "c") == "x"
    assert text_param({"a": 7}, "a") == "7"
    assert text_param({"a": ""}, "a", "b") is None


CLONE = "com.example.clone"


@pytest.mark.parametrize("payload, package", [
    ({"packageName": CLONE}, CLONE),
    ({"package_name": CLONE}, CLONE),
    ({"packageName": f" {CLONE} "}, CLONE),
    ({"packageName": "  "}, None),
    ({"packageName": "", "package_name": CLONE}, CLONE),
    ({"packageName": CLONE, "package_name": "com.other"}, CLONE),
    ({}, None),
], ids=["wire-key", "cli-name", "padded", "blank", "empty-wire-key", "wire-key-first", "absent"])
def test_the_clone_of_a_run_is_read_once_for_every_platform(payload, package):
    assert package_name_from_payload(payload) == package


# The clone's field read from a mapping anywhere in the bot and its bridges, outside its reader; the
# contract declares the field, it does not read it.
PACKAGE_KEYS = {"packageName", "package_name"}
NOT_A_READING = {"getattr", "hasattr", "setattr", "delattr"}


def _bot_files() -> list:
    files = []
    for root in ("taktik", "bridges"):
        for path in sorted((CORE / root).rglob("*.py")):
            if path.relative_to(CORE).parts[:3] != ("taktik", "core", "contract"):
                files.append(path)
    return files


def _is_package_key(node) -> bool:
    return isinstance(node, ast.Constant) and node.value in PACKAGE_KEYS


def _package_readings(tree: ast.AST) -> list[int]:
    """Lines that read the clone's field from a mapping: `.get`/`.pop`/`.setdefault`, `[...]`, `in`, or a
    helper handed the key (`value_param(payload, "packageName")`). Writing the key (a dict literal) is
    not a reading."""
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) and _is_package_key(node.slice):
            lines.append(node.lineno)
        elif isinstance(node, ast.Compare) and _is_package_key(node.left) and any(
                isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
            lines.append(node.lineno)
        elif isinstance(node, ast.Call) and any(_is_package_key(arg) for arg in node.args):
            name = node.func.id if isinstance(node.func, ast.Name) else None
            if name not in NOT_A_READING:
                lines.append(node.lineno)
    return sorted(set(lines))


def _readings(path) -> list[int]:
    return _package_readings(ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path)))


def test_no_code_reads_the_clone_outside_its_reader():
    files = _bot_files()
    # A blind gate would be green: it must see the bot, and the reading in the reader itself.
    assert HOME in files and len(files) > 1000, "the bot is no longer where this test looks"
    assert _readings(HOME), "the reader no longer reads the field the way this test looks for"
    found = [f"{path.relative_to(CORE).as_posix()}:{line}"
             for path in files if path != HOME for line in _readings(path)]
    assert not found, (
        "read the clone with `package_name_from_payload` (taktik/core/kernel/handler_params.py), or take "
        "the package the launcher hands to `connect`: " + ", ".join(found)
    )


@pytest.mark.parametrize("source, lines", [
    ('package = config.get("packageName")\n', [1]),
    ('package = payload.pop("package_name", None)\n', [1]),
    ('package = payload["packageName"]\n', [1]),
    ('if "packageName" in payload:\n    pass\n', [1]),
    ('package = value_param(merged, "package_name")\n', [1]),
    ('package = _first_given(payload.get("packageName"), payload.get("package_name"))\n', [1]),
    ('report = {"packageName": package}\n', []),
    ('package = getattr(automation, "package_name", None)\n', []),
    ('payload["packageName"] = package\n', []),
], ids=["get", "pop", "subscript", "in", "helper", "first-given", "written", "attribute", "assigned"])
def test_the_structural_check_sees_a_reading_by_hand(source, lines):
    assert _package_readings(ast.parse(source)) == lines
