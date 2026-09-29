"""Layer boundaries of the engine: who may import whom.

The layers of `taktik/core` (AGENTS.md, "Taxonomie cible"): `social_media/<platform>` is the
business code of one platform, `shared` the technical primitives, `database` the persistence,
`agent`, `app`, `clone`, `compat` the transverse families. `bridges/` and the CLI are the two hosts
that drive the core. Each rule below is a contract, red when a module imports what it may not:

- `shared-no-platform`: `shared` imports no platform ("Un module `shared` ne doit pas importer
  `social_media/<platform>`").
- `platforms-independent`: a platform imports no other platform. Code two platforms share is
  transverse, and a transverse helper does not live in a platform; a module of one platform lives
  under that platform.
- `transverse-no-platform`: `agent`, `app`, `clone`, `compat`, the `taktik.core` package itself and
  the rest of `taktik` outside the CLI import no platform: a module of a top-level family that is
  in fact specific to one platform lives under that platform.
- `core-no-host`: nothing under `taktik.core` imports `bridges` or the CLI. The host injects its
  notifier, IPC or AI service; the core stays usable without the desktop app.
- `database-no-upper-layer`: `database` imports no platform, no `compat` nor `clone`, no host
  (no Android workflow, selector, clone branch or bridge logic in the persistence).
- `sql-in-database`: `sqlite3` and `sqlalchemy` are imported under `taktik.core.database` only,
  in `taktik` and `bridges` (writes go through a repository or service of `database`).
- `cli-no-bridges`: the CLI imports no bridge. It is the reference the app mirrors (anti-derive
  rule 2), and it reaches device primitives through `bridges/common/device` only because they
  live there today; the two hosts that do are named in `EXCEPTIONS` and move with `device`.
- `known-core-families`: `taktik/core` holds only the families above; a new root family documents
  its owner in AGENTS.md first, then joins the contracts here.
- `import-resolves`: every import of our own packages (`taktik`, `bridges`) names a module that
  exists, in `taktik`, `bridges`, `scripts` and `tests/unit`: a file or a package holding Python
  files (a folder left with its caches only is not one), and for `from x import y`, `y` is a
  submodule of `x` or a name `x` defines. A lazy import in a function is read like the others:
  five of them pointed at modules moved away and failed only when their line ran, one of them the
  send of every welcome DM. Only a test may import what does not exist, under
  `pytest.raises(ImportError)` (it proves a module is gone).
- `no-deep-relative`: no new relative import of three dots or more. `from .....core.utils` is
  not rewritten when the tree moves, and nothing reads it until the line runs; an absolute import
  says where it goes. Ratchet (`scripts/audits/ratchet.py`): `scripts/audits/audit_import_layers_baseline.json`
  counts them per file, the counts only go down (`--update-baseline` records a decrease).

An import is what `python_imports.py` reads: every `import` / `from ... import`, lazy or under
`TYPE_CHECKING` included, relative ones resolved, and `import_module` / `__import__` with a literal
name. Direct imports only, as the rules say "import". The layer contracts read `taktik` and
`bridges`; `import-resolves` reads the scripts and the tests too. With these contracts together, an indirect
path from `shared`, `database` or a platform to a platform crosses a direct edge that one of them
forbids or that `EXCEPTIONS` names.

`EXCEPTIONS` names each file that crosses a boundary today, with its ceiling (import statements
across the boundary) and why it holds. Red when a file crosses a boundary without an entry, when
a listed file crosses it more than its ceiling, less (lower the ceiling), or no more (drop the
entry): the list only shrinks. Blind spots, said: a module name built at run time; a name given by `from x import *` or by a
module `__getattr__` (such a module accepts any name).

    python scripts/audits/audit_import_layers.py                    # green / red
    python scripts/audits/audit_import_layers.py --self-test        # each kind of forbidden import turns it red
    python scripts/audits/audit_import_layers.py --update-baseline  # record fewer deep relative imports
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Mapping

from python_imports import ImportStatement, defined_names, import_statements, module_name
from ratchet import Ratchet, compare, enforce

CORE = Path(__file__).resolve().parents[2]
SCAN_ROOTS = ("taktik", "bridges")
#: Read by `import-resolves` only: their imports of our packages must resolve too.
RESOLVE_ONLY_ROOTS = ("scripts", "tests/unit")
#: The packages whose imports the gate resolves; any other one is a dependency of the environment.
OWN_PACKAGES = frozenset({"taktik", "bridges"})
#: A relative import with this many dots or more is `no-deep-relative`.
DEEP_RELATIVE_DOTS = 3
#: What a test expects an import to raise when it proves a module is gone.
IMPORT_ERRORS = frozenset({"ImportError", "ModuleNotFoundError"})

DEEP_RELATIVE = Ratchet(
    label="Deep relative imports",
    noun=f"relative import(s) of {DEEP_RELATIVE_DOTS} dots or more",
    remedy="Write the import absolute (`from taktik.core.social_media...`).",
    command="python scripts/audits/audit_import_layers.py",
    baseline=CORE / "scripts" / "audits" / "audit_import_layers_baseline.json",
)

PLATFORMS = "social_media"
CORE_FAMILIES = frozenset({"agent", "app", "clone", "compat", "database", "shared", PLATFORMS})
TRANSVERSE = frozenset({"core", "agent", "app", "clone", "compat", "taktik"})
HOSTS = frozenset({"bridges", "cli"})
SQL_DRIVERS = frozenset({"sqlite3", "sqlalchemy"})


def family(name: str) -> str:
    """The layer a dotted name belongs to: `shared`, `social_media/tiktok`, `bridges`, `cli`, ...

    `core` is the `taktik.core` package itself, `taktik` the rest of `taktik` outside the core and
    the CLI; a name outside `taktik` and `bridges` is its top-level package (`sqlite3`).
    """
    parts = name.split(".")
    if parts[0] == "bridges":
        return "bridges"
    if parts[0] != "taktik":
        return parts[0]
    if len(parts) > 1 and parts[1] == "cli":
        return "cli"
    if parts[1:2] != ["core"]:
        return "taktik"
    if len(parts) == 2:
        return "core"
    if parts[2] == PLATFORMS and len(parts) > 3:
        return f"{PLATFORMS}/{parts[3]}"
    return parts[2]


def is_platform(name: str) -> bool:
    return name.startswith(f"{PLATFORMS}/")


def in_core(name: str) -> bool:
    return name == "core" or name in CORE_FAMILIES or is_platform(name)


@dataclass(frozen=True)
class Contract:
    name: str
    rule: str
    forbids: Callable[[str, str], bool]  # (importer family, imported family)


CONTRACTS = (
    Contract("shared-no-platform", "`shared` never imports a platform",
             lambda src, dst: src == "shared" and (is_platform(dst) or dst == PLATFORMS)),
    Contract("platforms-independent", "a platform never imports another platform",
             lambda src, dst: is_platform(src) and is_platform(dst) and src != dst),
    Contract("transverse-no-platform", "a transverse family never imports a platform",
             lambda src, dst: src in TRANSVERSE and (is_platform(dst) or dst == PLATFORMS)),
    Contract("core-no-host", "the core never imports a host (`bridges`, the CLI)",
             lambda src, dst: in_core(src) and dst in HOSTS),
    Contract("database-no-upper-layer", "`database` imports no platform, `compat`, `clone` nor host",
             lambda src, dst: src == "database" and (is_platform(dst) or dst in {PLATFORMS, "compat", "clone"} | HOSTS)),
    Contract("sql-in-database", "a SQL driver is imported under `taktik.core.database` only",
             lambda src, dst: src != "database" and dst in SQL_DRIVERS),
    Contract("cli-no-bridges", "the CLI imports no bridge",
             lambda src, dst: src == "cli" and dst == "bridges"),
)

#: (contract, file): (ceiling, why it holds and what removes it). The list only shrinks.
EXCEPTIONS: dict[tuple[str, str], tuple[int, str]] = {
    ("cli-no-bridges", "taktik/cli/hosts/instagram.py"): (
        10, "The Instagram host of the CLI opens its session through `bridges.common.device` "
            "(connection, app lifecycle, IP rotation) and `bridges.instagram.runtime.bridge`, the "
            "device primitives the CLI and the bridges share. They belong in `shared/device` "
            "(AGENTS.md makes it their owner); moving them there removes the entry."),
    ("cli-no-bridges", "taktik/cli/hosts/tiktok.py"): (
        1, "The TikTok host of the CLI reads the device through `bridges.common.device`, for the "
           "same reason as the Instagram host; moving `device` into `shared/device` removes it."),
    ("transverse-no-platform", "taktik/core/compat/selectors/setup.py"): (
        2, "By construction today: the version override registry registers the selector catalogs of "
           "Instagram and TikTok, and `shared/device/manager.py` applies it on connection (the "
           "\"exception de compat\" AGENTS.md allows `shared`). Inverting it, each platform "
           "registering its own catalogs, removes the entry."),
}


@dataclass(frozen=True)
class SourceModule:
    path: str
    name: str
    statements: tuple[ImportStatement, ...]
    error: str | None = None
    #: What `from <this module> import name` can reach (`defined_names`); None: any name.
    defines: frozenset[str] | None = None
    #: Lines of the imports a test expects to fail (under `pytest.raises(ImportError)`).
    expected_to_fail: frozenset[int] = frozenset()


def _lines_expected_to_fail(tree: ast.Module) -> frozenset[int]:
    """The lines inside a `with pytest.raises(ImportError)` block (or `ModuleNotFoundError`)."""
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.With, ast.AsyncWith)):
            continue
        for item in node.items:
            call = item.context_expr
            if not isinstance(call, ast.Call) or not call.args:
                continue
            func = call.func
            called = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
            first = call.args[0]
            expected = first.elts if isinstance(first, ast.Tuple) else [first]
            if called == "raises" and any(isinstance(e, ast.Name) and e.id in IMPORT_ERRORS for e in expected):
                lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return frozenset(lines)


def read_module(path: str, source: str) -> SourceModule:
    name, is_package = module_name(path)
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return SourceModule(path, name, (), f"does not parse ({exc.msg}, line {exc.lineno})")
    return SourceModule(path, name, tuple(import_statements(tree, name, is_package)),
                        defines=defined_names(tree), expected_to_fail=_lines_expected_to_fail(tree))


def read_tree() -> dict[str, SourceModule]:
    modules = {}
    for root in SCAN_ROOTS + RESOLVE_ONLY_ROOTS:
        for file in sorted((CORE / root).rglob("*.py")):
            if "__pycache__" in file.parts:
                continue
            path = file.relative_to(CORE).as_posix()
            modules[path] = read_module(path, file.read_text(encoding="utf-8-sig"))
    return modules


def in_layers(path: str) -> bool:
    """Is the file under the roots the layer contracts read (`taktik`, `bridges`)?"""
    return path.split("/")[0] in SCAN_ROOTS


def importable_names(modules: Mapping[str, SourceModule]) -> frozenset[str]:
    """Every module and package the tree holds, by dotted name: what an import can name.

    A module exists when a file of the tree has its name; a package, when a module lives under it
    (a regular package or a folder of Python files). The tree is what `read_tree` read, so a
    folder that only kept its `__pycache__` after a move is no package: in the checkout, Python
    would still import it (a namespace package), and hide the move.
    """
    names = {module.name for module in modules.values()}
    return frozenset(names | {name.rsplit(".", depth)[0] for name in names for depth in range(1, name.count(".") + 1)})


def unresolved_imports(modules: Mapping[str, SourceModule]) -> list[str]:
    """`import-resolves`: each import of `taktik` / `bridges` that names nothing in the tree."""
    by_name = {module.name: module for module in modules.values()}
    exists = importable_names(modules).__contains__

    failures = []
    for path, module in sorted(modules.items()):
        for statement in module.statements:
            if statement.line in module.expected_to_fail:
                continue
            for target in statement.modules:
                if target.split(".")[0] not in OWN_PACKAGES:
                    continue
                if not exists(target):
                    failures.append(f"{path}:{statement.line} imports {target}, which does not exist (import-resolves)")
                    continue
                source = by_name.get(target)
                for name in statement.names:
                    if exists(f"{target}.{name}"):
                        continue
                    if source is not None and (source.defines is None or name in source.defines):
                        continue
                    failures.append(f"{path}:{statement.line} imports {name} from {target}, which neither "
                                    f"defines it nor has such a submodule (import-resolves)")
    return failures


def deep_relative_counts(modules: Mapping[str, SourceModule]) -> dict[str, int]:
    """`no-deep-relative`: per file of `taktik` and `bridges`, its relative imports of 3 dots or more."""
    counts: dict[str, int] = {}
    for path, module in modules.items():
        if not in_layers(path):
            continue
        deep = sum(1 for statement in module.statements if statement.level >= DEEP_RELATIVE_DOTS)
        if deep:
            counts[path] = deep
    return counts


def crossings(module: SourceModule) -> dict[str, list[tuple[int, str]]]:
    """Contract name -> (line, imported name) of each statement of the module it forbids."""
    source = family(module.name)
    found: dict[str, list[tuple[int, str]]] = {}
    for statement in module.statements:
        for contract in CONTRACTS:
            names = sorted((t for t in statement.targets if contract.forbids(source, family(t))), key=len)
            if names:
                found.setdefault(contract.name, []).append((statement.line, names[0]))
    return found


def check(modules: Mapping[str, SourceModule],
          exceptions: Mapping[tuple[str, str], tuple[int, str]] = EXCEPTIONS) -> list[str]:
    failures: list[str] = []
    rules = {contract.name: contract.rule for contract in CONTRACTS}
    counted: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for path, module in sorted(modules.items()):
        if module.error:
            failures.append(f"{path} {module.error}: its imports cannot be read")
            continue
        if not in_layers(path):
            continue
        own = family(module.name)
        if module.name.startswith("taktik.core.") and not in_core(own):
            failures.append(f"{path}: `taktik/core/{own}` is not a known family of the core. Document its "
                            f"owner in AGENTS.md (Taxonomie cible), then add it to CORE_FAMILIES.")
        for contract, hits in crossings(module).items():
            counted[(contract, path)] = hits

    for key in sorted(set(counted) | set(exceptions)):
        contract, path = key
        hits = counted.get(key, [])
        if key not in exceptions:
            for line, name in hits:
                failures.append(f"{path}:{line} imports {name}: {rules[contract]} ({contract})")
            continue
        ceiling, _why = exceptions[key]
        if path not in modules:
            failures.append(f"{path} ({contract}) no longer exists: drop the entry")
        elif not hits:
            failures.append(f"{path} ({contract}) no longer crosses the boundary: drop the entry")
        elif len(hits) > ceiling:
            lines = ", ".join(str(line) for line, _ in hits)
            failures.append(f"{path} ({contract}) imports across the boundary {len(hits)} times, ceiling "
                            f"{ceiling} (lines {lines}): {rules[contract]}")
        elif len(hits) < ceiling:
            failures.append(f"{path} ({contract}) went down to {len(hits)} (ceiling {ceiling}): lower the ceiling")
    return failures + unresolved_imports(modules)


def main() -> int:
    update = "--update-baseline" in sys.argv
    modules = read_tree()
    failures = check(modules)
    verdict = enforce(deep_relative_counts(modules), DEEP_RELATIVE, update=update, other_failures=failures)
    if failures:
        print(f"Import layers: {len(failures)} finding(s). The rules are in this script's docstring; "
              f"a boundary crossed today is named in EXCEPTIONS with its reason.")
    elif verdict == 0 and not update:
        print(f"Import layers OK ({len(modules)} modules, {len(CONTRACTS)} contracts, "
              f"{len(EXCEPTIONS)} named exception(s), every import resolves)")
    return verdict


def _with_extra_import(module: SourceModule, target: str) -> SourceModule:
    return replace(module, statements=module.statements + (ImportStatement(99999, frozenset({target})),))


def self_test_cases(modules: Mapping[str, SourceModule]) -> dict[str, dict]:
    """Each fake must turn the gate red by the rule it breaks; the real tree, unchanged, must not."""
    def fake(path: str, source: str, expect: str) -> dict:
        return {"modules": {**modules, path: read_module(path, source)}, "expect": expect}

    def listed(module: SourceModule, expect: str) -> dict:
        return {"modules": {**modules, module.path: module}, "expect": expect}

    one = modules["taktik/core/ai/comments/generation.py"]
    two = modules["taktik/core/compat/selectors/setup.py"]
    without_tiktok = tuple(s for s in two.statements
                           if not any(t.startswith("taktik.core.social_media.tiktok") for t in s.targets))
    return {
        "shared imports a platform": fake(
            "taktik/core/shared/fake.py", "from taktik.core.social_media.instagram.ui import selectors\n",
            "(shared-no-platform)"),
        "shared imports a platform by a relative import": fake(
            "taktik/core/shared/device/fake.py", "from ...social_media.tiktok.ui import selectors\n",
            "(shared-no-platform)"),
        "shared imports a platform lazily": fake(
            "taktik/core/shared/fake.py", "def f():\n    import taktik.core.social_media.youtube.workflows\n",
            "(shared-no-platform)"),
        "shared imports a platform by name": fake(
            "taktik/core/shared/fake.py",
            "import importlib\nimportlib.import_module('taktik.core.social_media.threads.core')\n",
            "(shared-no-platform)"),
        "a platform imports another": fake(
            "taktik/core/social_media/tiktok/fake.py", "from taktik.core.social_media.instagram.ui import selectors\n",
            "(platforms-independent)"),
        "a new platform imports an existing one": fake(
            "taktik/core/social_media/newplatform/fake.py", "import taktik.core.social_media.tiktok.core\n",
            "(platforms-independent)"),
        "a transverse family imports a platform": fake(
            "taktik/core/clone/fake.py", "from taktik.core.social_media.instagram import ui\n",
            "(transverse-no-platform)"),
        "the core imports a bridge": fake(
            "taktik/core/social_media/instagram/fake.py", "from bridges.common.runtime.ipc import IPC\n",
            "(core-no-host)"),
        "the core imports the CLI": fake("taktik/core/agent/fake.py", "import taktik.cli.main\n", "(core-no-host)"),
        "database imports compat": fake(
            "taktik/core/database/fake.py", "from taktik.core.compat.selectors import setup\n",
            "(database-no-upper-layer)"),
        "a SQL driver in a platform": fake(
            "taktik/core/social_media/tiktok/fake.py", "import sqlite3\n", "(sql-in-database)"),
        "a SQL driver in a bridge": fake("bridges/common/fake.py", "from sqlalchemy import text\n", "(sql-in-database)"),
        "a new root family under the core": fake("taktik/core/utils/fake.py", "X = 1\n", "not a known family"),
        "a file that does not parse": fake("taktik/core/shared/fake.py", "def (\n", "does not parse"),
        "a listed file imports once more": listed(
            _with_extra_import(one, "taktik.core.social_media.tiktok.core"), "times, ceiling"),
        "a listed file no longer crosses": listed(replace(one, statements=()), "no longer crosses"),
        "a listed file crosses less than its ceiling": listed(
            replace(two, statements=without_tiktok), "lower the ceiling"),
        "a listed file removed": {
            "modules": {p: m for p, m in modules.items() if p != one.path}, "expect": "no longer exists"},
        "the CLI imports a bridge": fake(
            "taktik/cli/commands/fake.py", "from bridges.common.runtime.ipc import IPC\n", "(cli-no-bridges)"),
        "an import of a module that does not exist": fake(
            "taktik/core/shared/fake.py", "from taktik.core.shared.no_such_module import thing\n",
            "(import-resolves)"),
        "a lazy relative import of a module moved away": fake(
            "taktik/core/social_media/tiktok/actions/atomic/interaction/fake.py",
            "def f():\n    from ...detection.video_detector import VideoDetector\n", "(import-resolves)"),
        "a name its module does not define": fake(
            "bridges/common/fake.py", "from taktik.core.shared.text import no_such_name\n", "(import-resolves)"),
        "a test imports a module that does not exist": fake(
            "tests/unit/fake_test.py",
            "try:\n    from bridges.tiktok.engagement.runtime import no_such_module\nexcept ImportError:\n    pass\n",
            "(import-resolves)"),
        "a module named by its literal name that does not exist": fake(
            "scripts/fake.py", "import importlib\nimportlib.import_module('taktik.core.no_such_family')\n",
            "(import-resolves)"),
    }


def deep_relative_caught(modules: Mapping[str, SourceModule]) -> bool:
    """A new relative import of 3 dots turns the ratchet red, against the counts of the real tree."""
    path = "taktik/core/social_media/tiktok/actions/atomic/interaction/fake.py"
    fake = {**modules, path: read_module(path, "from ...core.utils import parse_count\n")}
    failures, _stale = compare(deep_relative_counts(fake), deep_relative_counts(modules), DEEP_RELATIVE.noun)
    return any(path in failure for failure in failures)


def caught(fake: dict) -> bool:
    return any(fake["expect"] in failure for failure in check(fake["modules"]))


def self_test() -> int:
    modules = read_tree()
    cases = self_test_cases(modules)
    missed = [name for name, fake in cases.items() if not caught(fake)]
    if not deep_relative_caught(modules):
        missed.append("a new relative import of 3 dots")
    control = check(modules)
    if missed or control:
        for name in missed:
            print(f"Self-test FAILED, not caught: {name}")
        for failure in control:
            print(f"Self-test FAILED, the real tree is red: {failure}")
        return 1
    print(f"Import layers self-test OK ({len(cases)} fakes caught, the real tree green)")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test() if "--self-test" in sys.argv else main())
