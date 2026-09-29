"""Patching a name the product code copies, without leaving the double behind.

A rig replaces a seam at its source (`taktik.core.ai.factory.build_ai_service`). Some modules
copy that name when they are imported (`from taktik.core.ai.factory import build_ai_service`).
If such a module is imported for the first time WHILE the source holds the double, it keeps the
double: `monkeypatch` puts back the source, not the copy, and every test collected afterwards runs
on the double (12 contract tests failed that way behind the one-path rigs).

`patch_seam` finds the modules that copy the name at import time (read from the source tree, a
copy of a copy included), imports them first, then patches the source and each copy: the copies
are real when saved, so `monkeypatch` puts them back. The guard of `tests/unit/conftest.py` fails
any test that still leaves a double in a module it imported.
"""
from __future__ import annotations

import ast
import importlib
from functools import lru_cache
from unit.paths import CORE

PRODUCT_ROOTS = (CORE / "taktik", CORE / "bridges")


def _import_time_statements(body):
    """The statements Python runs when it imports the module: not the bodies of functions."""
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield node
        for field in ("body", "orelse", "finalbody", "handlers"):
            children = getattr(node, field, None)
            if isinstance(children, list):
                yield from _import_time_statements(children)


@lru_cache(maxsize=None)
def _sources(roots: tuple) -> tuple:
    """(module name, is a package, text) of every Python file under the roots."""
    found = []
    for root in roots:
        for path in root.rglob("*.py"):
            parts = path.relative_to(root.parent).with_suffix("").parts
            package = parts[-1] == "__init__"
            module = ".".join(parts[:-1] if package else parts)
            found.append((module, package, path.read_text(encoding="utf-8-sig")))
    return tuple(found)


@lru_cache(maxsize=None)
def _tree(text: str) -> ast.Module:
    return ast.parse(text)


def _absolute(module: str, package: bool, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    base = module.split(".") if package else module.split(".")[:-1]
    base = base[: len(base) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


@lru_cache(maxsize=None)
def copiers(source: str, name: str, roots: tuple = PRODUCT_ROOTS) -> tuple:
    """The modules that copy `source.name` when they are imported, and those that copy them."""
    direct = []
    for module, package, text in _sources(roots):
        if name not in text or module == source:
            continue
        for node in _import_time_statements(_tree(text).body):
            if isinstance(node, ast.ImportFrom) and _absolute(module, package, node) == source \
                    and any(alias.name == name and alias.asname in (None, name) for alias in node.names):
                direct.append(module)
                break
    found = list(direct)
    for module in direct:
        found.extend(m for m in copiers(module, name, roots) if m not in found)
    return tuple(found)


def patch_seam(monkeypatch, source: str, name: str, value, roots: tuple = PRODUCT_ROOTS,
               copies: bool = True) -> None:
    """Replace `source.name` by `value` for the test, in the source and in every module that copies it.

    `copies=False` replaces the source only: the copies are still imported first, so they keep the
    real one whatever the order of the tests (a rig whose run needs the real service where the
    code copied it).
    """
    imported = []
    for module in copiers(source, name, roots):
        try:
            imported.append(importlib.import_module(module))
        except ImportError:
            # A module that cannot be imported here cannot capture the double either.
            continue
    monkeypatch.setattr(importlib.import_module(source), name, value)
    for module in imported if copies else ():
        if hasattr(module, name):
            monkeypatch.setattr(module, name, value)
