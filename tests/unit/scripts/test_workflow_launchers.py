"""One launcher per workflow: the gate is green on the tree and red on each fake second launcher."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import workflow_launchers  # noqa: E402


@pytest.fixture(scope="module")
def inputs():
    return workflow_launchers.collect_inputs()


@pytest.fixture(scope="module")
def baseline(inputs):
    return set(workflow_launchers.run_checks(inputs))


def test_the_tree_has_one_launcher_per_workflow(baseline):
    assert sorted(baseline) == []


@pytest.mark.parametrize("case", [
    "bridge builds an engine",
    "CLI calls an engine function",
    "handler outside the manifest",
    "manifest id without launcher",
    "bridge reaches no launcher",
    "stale exception",
    "second launch service",
    "spawn outside the runner",
    "scheduler type outside the manifest",
])
def test_a_fake_second_launcher_turns_the_gate_red(inputs, baseline, case):
    cases = workflow_launchers.self_test_cases(inputs)
    if case not in cases:
        pytest.skip("app repository absent")
    variant, exceptions, expected = cases[case]
    new = [f for f in workflow_launchers.run_checks(variant, exceptions) if f not in baseline]
    assert any(expected in finding for finding in new), new


def test_every_exception_is_dated_and_justified():
    for kind, entries in workflow_launchers.EXCEPTIONS.items():
        for key, reason in entries.items():
            assert reason[:10].count("-") == 2 and reason[:4].isdigit(), (kind, key)
            assert len(reason) > 20, (kind, key)
