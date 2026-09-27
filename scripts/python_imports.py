"""What a Python module imports, read from its source: one reading shared by the gates.

An import is every `import x` and `from x import y`, wherever it sits (a function body, a
`TYPE_CHECKING` block: a lazy import is still a dependency), relative ones resolved against the
module's package, and `importlib.import_module("x")` / `__import__("x")` when the name is a
literal (for an f-string, its literal prefix up to the last dot). A name built at run time is not
seen.

`from x import y` yields `x` and `x.y`: `y` may be a submodule, and a rule on packages matches
either way. A statement also says what must exist for it to run: `modules` (`x`, each module of
`import a.b, c`, the package of an f-string) and `names` (`y`: a submodule of `x`, or a name `x`
defines, see `defined_names`); `level` keeps the dots of a relative import.
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
    modules: tuple[str, ...] = ()
    names: tuple[str, ...] = ()
    level: int = 0  # the dots of a relative import


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
        modules: tuple[str, ...] = ()
        names: tuple[str, ...] = ()
        if isinstance(node, ast.Import):
            modules = tuple(alias.name for alias in node.names)
            targets = set(modules)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                base = ".".join(parts[: len(parts) - node.level + 1])
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            targets = {target} | {f"{target}.{alias.name}" for alias in node.names}
            modules = (target,)
            names = tuple(alias.name for alias in node.names if alias.name != "*")
        elif isinstance(node, ast.Call):
            dynamic = _dynamic_target(node)
            if dynamic:
                targets = {dynamic}
                modules = (dynamic,)
        if targets:
            level = node.level if isinstance(node, ast.ImportFrom) else 0
            statements.append(ImportStatement(node.lineno, frozenset(targets), modules, names, level or 0))
    return sorted(statements, key=lambda statement: statement.line)


def defined_names(tree: ast.Module) -> frozenset[str] | None:
    """The names a module binds at its top level, what `from module import name` can reach.

    A definition, an assignment, an import, a loop or `with` variable, at the top level or inside a
    top-level `if` / `try` / `with` / `for` / `while`; a `global` name assigned in a function. None
    when the module is open: a `from x import *` or a module `__getattr__` can give any name.
    """
    names: set[str] = set()

    def bind(target: ast.AST) -> None:
        for node in ast.walk(target):
            if isinstance(node, ast.Name):
                names.add(node.id)

    def visit(body: list[ast.stmt]) -> bool:
        for statement in body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(statement.name)
                for inner in ast.walk(statement):
                    if isinstance(inner, ast.Global):
                        names.update(inner.names)
            elif isinstance(statement, ast.Assign):
                for target in statement.targets:
                    bind(target)
            elif isinstance(statement, (ast.AnnAssign, ast.AugAssign)):
                bind(statement.target)
            elif isinstance(statement, ast.Import):
                names.update((alias.asname or alias.name).split(".")[0] for alias in statement.names)
            elif isinstance(statement, ast.ImportFrom):
                if any(alias.name == "*" for alias in statement.names):
                    return False
                names.update(alias.asname or alias.name for alias in statement.names)
            elif isinstance(statement, (ast.For, ast.AsyncFor)):
                bind(statement.target)
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                for item in statement.items:
                    if item.optional_vars is not None:
                        bind(item.optional_vars)
            if isinstance(statement, ast.Try):
                handlers = [handler.body for handler in statement.handlers]
                if not all(visit(block) for block in (statement.body, statement.orelse,
                                                       statement.finalbody, *handlers)):
                    return False
            elif isinstance(statement, (ast.If, ast.For, ast.AsyncFor, ast.While)):
                if not (visit(statement.body) and visit(statement.orelse)):
                    return False
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                if not visit(statement.body):
                    return False
        return True

    if not visit(tree.body) or "__getattr__" in names:
        return None
    return frozenset(names)
