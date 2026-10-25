"""What every Agent handler reads the same way: `taktik/core/kernel/handler_params.py`.

The merge of a step's params over the executor's payload has one home. A handler that writes the
two lines again (`merged = dict(payload)` then `merged.update(invocation.params)`) is a second way
to do it, and the structural test below names it.
"""

import ast

from taktik.core.kernel.contracts import WorkflowInvocation
from taktik.core.kernel.handler_params import merge_invocation_payload, value_param
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
