"""Find calls the CLI makes into code that no longer exists.

The CLI went unused for months while the rest of the bot kept moving. The failure mode that
produces is specific: a menu branch still calls a method that was removed, and nothing notices
until someone picks that menu entry. `automation._initialize_license_limits(api_key)` sat in the
Instagram automation branch and raised on every run started from the terminal — the method was
gone from `InstagramAutomation`, and the `api_key` it was handed had never been defined either.

Two checks, because they catch different things:

1. **Undefined names** — delegated to pyflakes, which finds them reliably. It would have caught
   the `api_key` half of that bug.
2. **Missing attributes** — pyflakes cannot see these. For every local built from a class this
   audit can resolve (`x = SomeClass(...)`, then `x.method(...)`), the attribute is checked
   against the real class. That is the half pyflakes missed.

Both are limited on purpose. Check 2 only follows locals assigned from a directly-imported class,
because anything cleverer starts guessing and a guessing audit gets ignored. Reporting fewer, true
findings beats reporting many uncertain ones.

Exit code is 1 when something is found, so this one CAN gate: an attribute that does not exist is
a crash, not a matter of taste.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TARGETS = [ROOT / "taktik" / "cli"]


def python_files() -> list[Path]:
    out: list[Path] = []
    for target in TARGETS:
        out.extend(p for p in target.rglob("*.py") if "__pycache__" not in str(p))
    return sorted(out)


# --- check 1: undefined names ----------------------------------------------

def undefined_names() -> list[str]:
    """Delegate to pyflakes; absence of the tool is reported, never silently skipped."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pyflakes", *[str(p) for p in TARGETS]],
            capture_output=True, text=True, cwd=ROOT,
        )
    except FileNotFoundError:  # pragma: no cover
        return ["pyflakes is not installed; undefined-name check skipped"]

    if proc.returncode not in (0, 1):
        return [f"pyflakes failed: {proc.stderr.strip()}"]

    return [line for line in proc.stdout.splitlines() if "undefined name" in line]


# --- check 2: attributes that do not exist ---------------------------------

def _imported_classes(tree: ast.Module) -> dict[str, str]:
    """Local alias -> dotted path, for `from x.y import Z` and `import x.y as z`."""
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                found[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found[alias.asname or alias.name] = alias.name
    return found


def _resolve(dotted: str):
    """Import `dotted` as a symbol, or return None if it cannot be resolved."""
    module_path, _, name = dotted.rpartition(".")
    if not module_path:
        return None
    try:
        module = importlib.import_module(module_path)
    except Exception:
        return None
    return getattr(module, name, None)


def _instance_attributes(cls: type) -> set[str]:
    """Names the class assigns to `self` anywhere in its own methods.

    `hasattr(cls, name)` only sees class-level attributes, so an ordinary `self.device = ...` in
    `__init__` would be reported as missing. Reading the source of the class recovers those and
    keeps the audit from crying wolf on every normal instance attribute.
    """
    names: set[str] = set()
    for klass in getattr(cls, "__mro__", [cls]):
        try:
            source = ast.parse(_dedent(inspect.getsource(klass)))
        except (OSError, TypeError, SyntaxError):
            continue
        for node in ast.walk(source):
            if (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store)
                    and isinstance(node.value, ast.Name) and node.value.id == "self"):
                names.add(node.attr)
    return names


def _dedent(source: str) -> str:
    import textwrap
    return textwrap.dedent(source)


def _display(path: Path) -> str:
    """Repo-relative when possible, absolute otherwise — a path outside the tree must not raise."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def missing_attributes(path: Path) -> list[str]:
    # utf-8-sig: several CLI modules start with a BOM, which ast.parse rejects outright — the
    # audit would have reported a syntax error instead of scanning the largest file.
    source = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"{_display(path)}: syntax error: {exc}"]

    imports = _imported_classes(tree)
    findings: list[str] = []
    seen: set[tuple[str, str]] = set()

    # Real scoping. A module-level `automation` click group and a local
    # `automation = InstagramAutomation(...)` inside a function are two different variables with
    # one name; without separating them, every `automation.command(...)` on the group is reported
    # as missing from the class. ast.walk from the module would re-absorb the function bodies, so
    # each node is assigned to its nearest enclosing function instead.
    owner: dict[int, ast.AST] = {}

    def _claim(scope: ast.AST, node: ast.AST, skip: set[int] | None = None) -> None:
        for child in ast.iter_child_nodes(node):
            if skip and id(child) in skip:
                continue
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Decorators belong to the ENCLOSING scope, the body to the function. They must be
                # skipped when descending into the function, or the second pass reassigns them to
                # it — which is what made every `@automation.command(...)` look like a call on the
                # InstagramAutomation instance built inside the decorated function.
                for decorator in child.decorator_list:
                    owner[id(decorator)] = scope
                    _claim(scope, decorator)
                owner[id(child)] = child
                _claim(child, child, skip={id(d) for d in child.decorator_list})
            else:
                owner[id(child)] = scope
                _claim(scope, child)

    owner[id(tree)] = tree
    _claim(tree, tree)

    by_scope: dict[int, list[ast.AST]] = {}
    for node in ast.walk(tree):
        scope = owner.get(id(node), tree)
        by_scope.setdefault(id(scope), []).append(node)

    for nodes in by_scope.values():
        locals_to_class: dict[str, type] = {}
        for node in nodes:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            func = node.value.func
            if not isinstance(func, ast.Name) or func.id not in imports:
                continue
            symbol = _resolve(imports[func.id])
            if not isinstance(symbol, type):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    locals_to_class[target.id] = symbol

        if not locals_to_class:
            continue

        for node in nodes:
            if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
                continue
            cls = locals_to_class.get(node.value.id)
            if cls is None:
                continue
            if hasattr(cls, node.attr) or node.attr in _instance_attributes(cls):
                continue
            # Assigning a new attribute is legal Python; only reads and calls are suspect.
            if isinstance(node.ctx, ast.Store):
                continue
            key = (node.value.id, node.attr)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                f"{_display(path)}:{node.lineno} "
                f"{node.value.id}.{node.attr} does not exist on {cls.__name__}"
            )
    return findings


def main() -> int:
    print("=" * 78)
    print("SANTE DE LA CLI")
    print("=" * 78)

    names = undefined_names()
    print(f"\n  noms indefinis        : {len(names)}")
    for line in names:
        print(f"    {line}")

    attribute_findings: list[str] = []
    for path in python_files():
        attribute_findings.extend(missing_attributes(path))

    print(f"  attributs inexistants : {len(attribute_findings)}")
    for line in attribute_findings:
        print(f"    {line}")

    total = len(names) + len(attribute_findings)
    print(f"\n  total : {total}")
    print()
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
