"""What a Python module imports, read from its source: one reading shared by the gates.

An import is every `import x` and `from x import y`, wherever it sits (a function body, a
`TYPE_CHECKING` block: a lazy import is still a dependency), relative ones resolved against the
module's package, and `importlib.import_module("x")` / `__import__("x")` when the name is a
literal (for an f-string, its literal prefix up to the last dot). A name built at run time is not
seen.

`from x import y` yields `x` and `x.y`: `y` may be a submodule, and a rule on packages matches
either way.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import PurePosixPath

DYNAMIC_IMPORTERS = frozenset({"import_module", "__import__"})


@dataclass(frozen=True)
class ImportStatement:
    line: int
    targets: frozenset[str]


def module_name(relative_path: str) -> tuple[str, bool]:
    """`taktik/core/shared/text.py` -> (`taktik.core.shared.text`, False); a package's `__init__.py` -> its name, True."""
    path = PurePosixPath(relative_path)
    parts = list(path.with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    return ".".join(parts), is_package


def _dynamic_target(call: ast.Call) -> str | None:
    func = call.func
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
    if name not in DYNAMIC_IMPORTERS or not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    if isinstance(first, ast.JoinedStr) and first.values:
        head = first.values[0]
        if isinstance(head, ast.Constant) and isinstance(head.value, str) and "." in head.value:
            return head.value.rpartition(".")[0]
    return None


def import_statements(tree: ast.Module, module: str, is_package: bool) -> list[ImportStatement]:
    """Each import of the module, with its line and the dotted names it reaches."""
    package = module if is_package else module.rpartition(".")[0]
    statements: list[ImportStatement] = []
    for node in ast.walk(tree):
        targets: set[str] = set()
        if isinstance(node, ast.Import):
            targets = {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - node.level + 1])
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            targets = {target} | {f"{target}.{alias.name}" for alias in node.names}
        elif isinstance(node, ast.Call):
            dynamic = _dynamic_target(node)
            if dynamic:
                targets = {dynamic}
        if targets:
            statements.append(ImportStatement(node.lineno, frozenset(targets)))
    return sorted(statements, key=lambda statement: statement.line)
