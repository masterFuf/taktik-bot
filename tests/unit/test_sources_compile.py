"""Every Python file of the repository compiles, on 3.10 as on 3.14, the Python of the installer.

From 3.13 the compiler strips the indentation of a docstring through UTF-8, and a docstring that
holds half of a UTF-16 pair (an escape such as `\\ud83d` in a docstring that is not raw) stops the
import with `UnicodeEncodeError: surrogates not allowed`. `taktik/core/shared/text.py` did: under
3.14 nothing that reads the base could be imported, the test suite and the frozen launcher included.
3.10 compiles such a docstring without a word, and `ast.parse` sees nothing either: the second test
reads the docstrings themselves, so the battery, which runs 3.10, turns red too.
"""

from __future__ import annotations

import ast

import pytest

from unit.paths import CORE

ROOTS = ("taktik", "bridges", "scripts", "tests")


def _sources():
    return sorted(path for root in ROOTS for path in (CORE / root).rglob("*.py"))


def _is_surrogate(char: str) -> bool:
    return 0xD800 <= ord(char) <= 0xDFFF


def _docstrings(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            text = ast.get_docstring(node, clean=False)
            if text is not None:
                yield getattr(node, "lineno", 1), text


@pytest.fixture(scope="module")
def sources():
    files = _sources()
    assert len(files) > 1000, "the walk no longer reaches the sources of the repository"
    return [(path, path.read_text(encoding="utf-8-sig")) for path in files]


def test_every_source_compiles_on_this_python(sources):
    refused = []
    for path, text in sources:
        try:
            compile(text, str(path), "exec", dont_inherit=True)
        except (SyntaxError, UnicodeError, ValueError) as error:
            refused.append(f"{path.relative_to(CORE)}: {type(error).__name__}: {error}")
    assert refused == []


def test_no_docstring_holds_half_of_a_utf16_pair(sources):
    found = []
    for path, text in sources:
        for line, docstring in _docstrings(ast.parse(text, filename=str(path))):
            if any(_is_surrogate(char) for char in docstring):
                found.append(f"{path.relative_to(CORE)}:{line}")
    assert found == []
