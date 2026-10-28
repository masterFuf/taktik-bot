"""The layer gate: the engine's imports keep to its layers, and each forbidden import turns it red.

The fakes live in the gate itself (`self_test_cases`), so the rules and their proofs stay together.
"""

import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/audits"))

import audit_import_layers as audit  # noqa: E402
from python_imports import import_statements, module_name  # noqa: E402

MODULES = audit.read_tree()
CASES = audit.self_test_cases(MODULES)


def test_the_engine_imports_keep_to_its_layers():
    assert audit.check(MODULES) == []


def test_the_deep_relative_baseline_is_the_tree():
    from ratchet import compare, load_baseline

    counts = audit.deep_relative_counts(MODULES)
    assert compare(counts, load_baseline(audit.DEEP_RELATIVE.baseline), audit.DEEP_RELATIVE.noun) == ([], [])


@pytest.mark.parametrize("name", CASES)
def test_each_forbidden_import_turns_the_gate_red_by_its_rule(name):
    assert audit.caught(CASES[name])


def test_a_new_deep_relative_import_turns_the_ratchet_red():
    assert audit.deep_relative_caught(MODULES)


def test_a_bridge_may_import_what_the_bridges_share():
    """`bridges/common/`, the `common/` of its platform, its own folder, the launcher and the core: no finding."""
    assert audit.shared_bridge_code_left_alone(MODULES)


def test_a_test_may_import_what_does_not_exist_to_prove_it_is_gone():
    path = "tests/unit/fake_test.py"
    source = ("import pytest\n\n"
              "def test_gone():\n"
              "    with pytest.raises(ImportError):\n"
              "        from taktik.core.shared import no_such_module  # noqa: F401\n")
    failures = audit.check({**MODULES, path: audit.read_module(path, source)})
    assert [failure for failure in failures if path in failure] == []


def test_a_name_given_by_a_star_import_is_not_a_finding():
    base = "taktik/core/shared/fake_star.py"
    user = "bridges/common/fake_user.py"
    modules = {
        **MODULES,
        base: audit.read_module(base, "from taktik.core.shared.text import *\n"),
        user: audit.read_module(user, "from taktik.core.shared.fake_star import anything\n"),
    }
    assert [failure for failure in audit.check(modules) if "fake_" in failure] == []


def test_a_relative_import_resolves_against_the_package():
    import ast

    name, is_package = module_name("taktik/core/shared/device/__init__.py")
    tree = ast.parse("from ..text import normalize\nfrom . import adb\n")
    targets = {t for s in import_statements(tree, name, is_package) for t in s.targets}
    assert {"taktik.core.shared.text", "taktik.core.shared.device.adb"} <= targets


def test_an_fstring_module_name_keeps_its_literal_package():
    import ast

    tree = ast.parse("__import__(f'taktik.core.shared.diagnostics.{name}')\n")
    statements = import_statements(tree, "bridges.common.entrypoint", False)
    assert [set(s.targets) for s in statements] == [{"taktik.core.shared.diagnostics"}]


# `no-facade-import`: a name is imported from its module, never through a package that re-exports it.

PROBE = "taktik/core/social_media/tiktok/workflows/cold_dm/probe.py"


def _facade_hits(source, path=PROBE):
    modules = {**MODULES, path: audit.read_module(path, source)}
    return audit.facade_imports(modules).get(path, [])


def test_the_facade_import_baseline_is_the_tree():
    from ratchet import compare, load_baseline

    counts = audit.facade_import_counts(MODULES)
    assert compare(counts, load_baseline(audit.FACADE_IMPORTS.baseline), audit.FACADE_IMPORTS.noun) == ([], [])


def test_a_new_facade_import_turns_the_ratchet_red_and_names_its_line():
    source = "import random\n\nfrom taktik.core.social_media.tiktok import TikTokManager\n"
    hits = _facade_hits(source)
    assert [(hit.line, hit.name, hit.package, hit.owner) for hit in hits] == [
        (3, "TikTokManager", "taktik.core.social_media.tiktok", "taktik.core.social_media.tiktok.manager")]
    assert audit.facade_import_caught(MODULES)


def test_a_relative_facade_import_is_counted_too():
    hits = _facade_hits("def f():\n    from ... import TikTokManager\n")
    assert [(hit.line, hit.name) for hit in hits] == [(2, "TikTokManager")]


def test_an_import_from_the_owner_module_is_not_a_facade_import():
    source = ("from taktik.core.social_media.tiktok.manager import TikTokManager\n"
              "from taktik.core.social_media.tiktok import manager\n"
              "from taktik.core.social_media.tiktok import __version__\n")
    assert _facade_hits(source) == []
