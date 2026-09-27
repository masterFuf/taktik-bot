"""The layer gate: the engine's imports keep to its layers, and each forbidden import turns it red.

The fakes live in the gate itself (`self_test_cases`), so the rules and their proofs stay together.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import audit_import_layers as audit  # noqa: E402
from python_imports import import_statements, module_name  # noqa: E402

MODULES = audit.read_tree()
CASES = audit.self_test_cases(MODULES)


def test_the_engine_imports_keep_to_its_layers():
    assert audit.check(MODULES) == []


@pytest.mark.parametrize("name", CASES)
def test_each_forbidden_import_turns_the_gate_red_by_its_rule(name):
    assert audit.caught(CASES[name])


def test_a_relative_import_resolves_against_the_package():
    import ast

    name, is_package = module_name("taktik/core/shared/device/__init__.py")
    tree = ast.parse("from ..text import normalize\nfrom . import adb\n")
    targets = {t for s in import_statements(tree, name, is_package) for t in s.targets}
    assert {"taktik.core.shared.text", "taktik.core.shared.device.adb"} <= targets


def test_an_fstring_module_name_keeps_its_literal_package():
    import ast

    tree = ast.parse("__import__(f'taktik.core.shared.diagnostics.{name}')\n")
    statements = import_statements(tree, "bridges.common.runtime.entrypoint", False)
    assert [set(s.targets) for s in statements] == [{"taktik.core.shared.diagnostics"}]
