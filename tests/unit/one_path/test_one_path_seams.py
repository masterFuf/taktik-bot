"""`patch_seam` leaves no double behind, where `monkeypatch.setattr` on the source alone does.

Two throwaway packages stand for the product code: `seam_source.tools.name` and two modules that
copy it when imported, one of them through a relative import and one through the first copy.
"""
from __future__ import annotations

import importlib
import sys

import pytest

from one_path_seams import copiers, patch_seam


@pytest.fixture
def product(tmp_path, monkeypatch):
    """A package whose copiers are imported for the first time during the test, like a bridge."""
    root = tmp_path / "seam_product"
    (root / "tools").mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "tools" / "__init__.py").write_text("from .names import name\n", encoding="utf-8")
    (root / "tools" / "names.py").write_text("def name():\n    return 'real'\n", encoding="utf-8")
    (root / "copy_one.py").write_text("from seam_product.tools.names import name\n", encoding="utf-8")
    (root / "copy_two.py").write_text(
        "try:\n    from seam_product.copy_one import name\nexcept ImportError:\n    raise\n", encoding="utf-8")
    (root / "late.py").write_text("def use():\n    from seam_product.tools.names import name\n    return name()\n",
                                  encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    yield (root,)
    for module in [m for m in sys.modules if m.split(".")[0] == "seam_product"]:
        del sys.modules[module]


def _fake():
    return "double"


def test_the_copies_are_found_through_relative_imports_and_copies_of_copies(product):
    assert set(copiers("seam_product.tools.names", "name", product)) == {
        "seam_product.tools", "seam_product.copy_one", "seam_product.copy_two"}


def test_a_copy_imported_under_a_plain_patch_keeps_the_double(product):
    names = importlib.import_module("seam_product.tools.names")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(names, "name", _fake)
        copy = importlib.import_module("seam_product.copy_one")
    assert copy.name is _fake


def test_patch_seam_puts_every_copy_back(product):
    with pytest.MonkeyPatch.context() as mp:
        patch_seam(mp, "seam_product.tools.names", "name", _fake, product)
        copy_two = importlib.import_module("seam_product.copy_two")
        assert copy_two.name() == "double"
        assert importlib.import_module("seam_product.late").use() == "double"
    for module in ("seam_product.tools.names", "seam_product.tools", "seam_product.copy_one", "seam_product.copy_two"):
        assert importlib.import_module(module).name() == "real", module
