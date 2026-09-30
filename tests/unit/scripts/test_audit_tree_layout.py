"""The tree layout gate: a folder of its table holds only what the table lists, a folder holds no more `.py`
files than its ceiling, and each misplaced entry turns it red.

The fakes live in the gate itself (`self_test_cases`), so the rules and their proofs stay together.
"""

import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/audits"))

import audit_tree_layout as audit  # noqa: E402
import ratchet  # noqa: E402

PATHS = audit.tree_paths()
CASES = audit.self_test_cases(PATHS)


def test_the_tree_keeps_to_its_table():
    assert audit.check(PATHS) == []


@pytest.mark.parametrize("name", CASES)
def test_each_misplaced_entry_turns_the_gate_red_by_its_rule(name):
    assert audit.caught(CASES[name])


def test_a_folder_at_its_ceiling_or_a_listed_folder_that_shrinks_or_goes_away_stays_green():
    assert audit.size_rule_left_alone(PATHS)


def test_the_list_of_the_oversized_folders_is_written_like_the_other_ratchets(tmp_path):
    written = tmp_path / "written.json"
    ratchet.write_baseline(ratchet.load_baseline(audit.SIZES.baseline), written)
    assert audit.SIZES.baseline.read_bytes() == written.read_bytes()
