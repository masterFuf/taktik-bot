"""The package installs what the engine needs, read from one list: `requirements.txt`.

`setup.py` kept its own list of eight requirements while `requirements.txt` named twenty, loguru
among them, which the engine imports in its first line: `pip install .` gave a package that could
not start. The two lists now are one (`setup.py` reads `requirements.txt`, as `composer.json`'s
`require` is the one list of a PHP package), and the tools of a developer (tests, formatters) are
in `requirements-dev.txt`, which includes the runtime list (`require-dev`).

The requirements the package declares are read from the metadata that setuptools writes
(`egg_info`), what pip installs from.

The runtime list says what the engine imports, both ways. Seven packages sat in it that nothing
imported (`typer`, `pydantic`, `schedule`, `python-dotenv`, `reportlab`, `cryptography`,
`pure-python-adb`), while `numpy` and `lxml`, imported, were not in it: they came with the Python
of the build machine, so a clean environment froze a launcher whose ad fingerprint returned `None`.
The imports are read as the gates read them (`scripts/audits/python_imports.py`: lazy and
literal `importlib` imports included) in `taktik/` and `bridges/`; what `requirements-media.txt`
lists (the mitmproxy addon) is optional and may be imported without being required.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement

from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/audits"))

from python_imports import import_statements, module_name  # noqa: E402

DEV_TOOLS = ("pytest", "pytest-cov", "setuptools", "black", "flake8", "isort")
BUILD_TOOLS = ("pyinstaller",)
#: The code the package installs; scripts/ and tests/ are tools, their packages are listed apart.
ENGINE_ROOTS = ("taktik", "bridges")
OWN_PACKAGES = ("taktik", "bridges", "__future__")
#: The import names that differ from the name of their distribution.
IMPORT_NAME_OF = {"pillow": "PIL", "pyyaml": "yaml"}


def _requirement_lines(path: Path) -> list[str]:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            lines.append(line)
    return lines


def _name(requirement: str) -> str:
    return Requirement(requirement).name.lower()


@pytest.fixture(scope="module")
def declared(tmp_path_factory) -> list[str]:
    """`install_requires` as the package metadata holds it."""
    base = tmp_path_factory.mktemp("egg")
    subprocess.run(
        [sys.executable, "setup.py", "-q", "egg_info", "--egg-base", str(base)],
        cwd=CORE, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    (info,) = base.glob("*.egg-info")
    return [line.strip() for line in (info / "requires.txt").read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _canonical(requirements) -> set:
    """Each requirement as (name, its version clauses): setuptools reorders the clauses."""
    return {(_name(line), frozenset(str(spec) for spec in Requirement(line).specifier))
            for line in requirements}


def test_the_package_requires_exactly_the_runtime_list(declared):
    runtime = _requirement_lines(CORE / "requirements.txt")

    assert _canonical(declared) == _canonical(runtime)


def test_the_package_requires_what_the_engine_imports_first(declared):
    assert "loguru" in {_name(requirement) for requirement in declared}


def test_the_runtime_list_holds_no_developer_tool():
    names = {_name(line) for line in _requirement_lines(CORE / "requirements.txt")}

    assert not names & set(DEV_TOOLS)


def test_the_developer_list_adds_its_tools_to_the_runtime_list():
    lines = _requirement_lines(CORE / "requirements-dev.txt")

    assert lines[0] == "-r requirements.txt"
    assert {_name(line) for line in lines[1:]} == set(DEV_TOOLS)


def test_the_build_list_adds_pyinstaller_to_the_runtime_list():
    lines = _requirement_lines(CORE / "requirements-build.txt")

    assert lines[0] == "-r requirements.txt"
    assert {_name(line) for line in lines[1:]} == set(BUILD_TOOLS)


def _third_party_imports() -> dict:
    """Each top-level module that `taktik/` and `bridges/` import and that is neither the standard
    library nor ours, with the files that import it."""
    imported: dict = {}
    for root in ENGINE_ROOTS:
        for path in sorted((CORE / root).rglob("*.py")):
            relative = path.relative_to(CORE).as_posix()
            module, is_package = module_name(relative)
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=relative)
            for statement in import_statements(tree, module, is_package):
                if statement.level:
                    continue
                for target in statement.modules:
                    top = target.split(".")[0]
                    if top and top not in sys.stdlib_module_names and top not in OWN_PACKAGES:
                        imported.setdefault(top, set()).add(relative)
    return imported


def _import_names(path: Path) -> set:
    names = {_name(line) for line in _requirement_lines(path) if not line.startswith("-")}
    return {IMPORT_NAME_OF.get(name, name).lower() for name in names}


def test_every_package_the_engine_imports_is_declared():
    declared = _import_names(CORE / "requirements.txt") | _import_names(CORE / "requirements-media.txt")
    imported = _third_party_imports()

    assert {top: sorted(files) for top, files in imported.items() if top.lower() not in declared} == {}


def test_every_runtime_requirement_is_imported_by_the_engine():
    imported = {top.lower() for top in _third_party_imports()}

    assert sorted(_import_names(CORE / "requirements.txt") - imported) == []
