"""Every module of ours a build definition names exists in the tree.

PyInstaller only warns about a `--hidden-import` it cannot find, and the build goes on: the spec named
`taktik.core.license`, `taktik.core.database.api_client` and
`taktik.core.license.unified_license_manager` long after they were deleted, and nothing said so. The
names are resolved as `audit_import_layers.py` resolves an import (`importable_names`: a folder left
with its caches only is no package). Three build definitions exist; each one is checked.
"""

import ast
import re
import sys
from pathlib import Path

import pytest
from unit.paths import CORE

BUILD_ALL = CORE.parent / "app" / "scripts" / "build" / "build-all.ps1"
sys.path.insert(0, str(CORE / "scripts/audits"))

import audit_import_layers as audit  # noqa: E402

#: What PyInstaller reads as a module name: an option's value, or an entry of a hidden-import list.
_OPTIONS = ("--hidden-import=", "--collect-submodules=", "--collect-all=")
_COLLECTORS = frozenset({"collect_submodules", "collect_all"})
_PS1_NAMED = re.compile(r'"--(?:hidden-import|collect-submodules|collect-all)=([\w.]+)"')


def _ours(names):
    return sorted({name for name in names if name.split(".")[0] in audit.OWN_PACKAGES})


def _strings(node):
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _named_by_python(path: Path):
    """The module names a Python build definition gives PyInstaller: its `--hidden-import=` /
    `--collect-*=` options, the entries of its hidden-import lists, the names it collects."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    names = [value.split("=", 1)[1] for value in _strings(tree) if value.startswith(_OPTIONS)]
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any("hidden" in t.id for t in node.targets if isinstance(t, ast.Name)):
            names += _strings(node.value)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _COLLECTORS:
            names += _strings(node)
    return _ours(names)


@pytest.fixture(scope="module")
def importable():
    return audit.importable_names(audit.read_tree())


@pytest.mark.parametrize("definition", ["taktik_launcher.spec", "scripts/build/build_exe.py"])
def test_the_core_build_definitions_name_modules_that_exist(definition, importable):
    named = _named_by_python(CORE / definition)

    assert named, f"{definition}: no module of ours read, the reader no longer sees its lists"
    assert [name for name in named if name not in importable] == []


@pytest.mark.skipif(not BUILD_ALL.is_file(), reason="the app repository is not beside core")
def test_the_app_build_names_modules_that_exist(importable):
    named = _ours(_PS1_NAMED.findall(BUILD_ALL.read_text(encoding="utf-8-sig")))

    assert named, "build-all.ps1: no module of ours read, the reader no longer sees its arguments"
    assert [name for name in named if name not in importable] == []
