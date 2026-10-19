"""The package installs what the engine needs, read from one list: `requirements.txt`.

`setup.py` kept its own list of eight requirements while `requirements.txt` named twenty, loguru
among them, which the engine imports in its first line: `pip install .` gave a package that could
not start. The two lists now are one (`setup.py` reads `requirements.txt`, as `composer.json`'s
`require` is the one list of a PHP package), and the tools of a developer (tests, formatters) are
in `requirements-dev.txt`, which includes the runtime list (`require-dev`).

The requirements the package declares are read from the metadata that setuptools writes
(`egg_info`), what pip installs from.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement

from unit.paths import CORE

DEV_TOOLS = ("pytest", "pytest-cov", "black", "flake8", "isort")


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
