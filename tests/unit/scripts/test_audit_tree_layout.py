"""The tree layout gate: a folder of its table holds only what the table lists, and each misplaced entry
turns it red.

The fakes live in the gate itself (`self_test_cases`), so the rules and their proofs stay together.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "audits"))

import audit_tree_layout as audit  # noqa: E402

PATHS = audit.tree_paths()
CASES = audit.self_test_cases(PATHS)


def test_the_tree_keeps_to_its_table():
    assert audit.check(PATHS) == []


@pytest.mark.parametrize("name", CASES)
def test_each_misplaced_entry_turns_the_gate_red_by_its_rule(name):
    assert audit.caught(CASES[name])
