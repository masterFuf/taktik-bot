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
- `known-core-families`: `taktik/core` holds only the families above; a new root family documents
  its owner in AGENTS.md first, then joins the contracts here.

An import is what `python_imports.py` reads: every `import` / `from ... import`, lazy or under
`TYPE_CHECKING` included, relative ones resolved, and `import_module` / `__import__` with a literal
name. Direct imports only, as the rules say "import". With these contracts together, an indirect
path from `shared`, `database` or a platform to a platform crosses a direct edge that one of them
forbids or that `EXCEPTIONS` names.

`EXCEPTIONS` names each file that crosses a boundary today, with its ceiling (import statements
across the boundary) and why it holds. Red when a file crosses a boundary without an entry, when
a listed file crosses it more than its ceiling, less (lower the ceiling), or no more (drop the
entry): the list only shrinks. Blind spot, said: a module name built at run time.

    python scripts/audit_import_layers.py              # green / red
    python scripts/audit_import_layers.py --self-test  # each kind of forbidden import turns it red
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Mapping

from python_imports import ImportStatement, import_statements, module_name

CORE = Path(__file__).resolve().parents[1]
SCAN_ROOTS = ("taktik", "bridges")

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
)

#: (contract, file): (ceiling, why it holds and what removes it). The list only shrinks.
EXCEPTIONS: dict[tuple[str, str], tuple[int, str]] = {
    ("transverse-no-platform", "taktik/core/__init__.py"): (
        1, "Public compatibility export `taktik.core.DeviceFacade`, lazy, that only its own test calls "
           "(tests/unit/core/test_core_exports.py). Removed with the export: a break of the package's "
           "public API, the owner's call."),
    ("transverse-no-platform", "taktik/core/agent/scenarios/instagram_feed_autopilot.py"): (
        17, "The Taktik Agent session (`TaktikAgentWorkflow`) drives Instagram from `agent/scenarios/`, "
            "the place AGENTS.md gives the legacy autopilots. A module of one platform lives under it: "
            "moving it to `social_media/instagram/workflows/agent/` removes the entry."),
    ("transverse-no-platform", "taktik/core/app/ai/comments/generation.py"): (
        1, "Comment generation, shared by Instagram and TikTok, reads the anchor rules from "
           "`social_media/instagram/workflows/common/comment_context` (lazily, to break an import "
           "loop): a TikTok run loads Instagram code. The anchor rules are not Instagram-specific; "
           "moving them under `app/ai/comments/` removes the entry."),
    ("transverse-no-platform", "taktik/core/app/email/gmail/workflows/agent_handler.py"): (
        1, "The Gmail Agent handlers reuse TikTok's internal adaptation helpers "
           "(`tiktok/actions/business/workflows/_internal/agent_runtime.py`), which AGENTS.md keeps for "
           "the handlers of one platform. Shared by two families, they belong with the handler "
           "contract (`agent/kernel/`); moving them removes the entry."),
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


def read_module(path: str, source: str) -> SourceModule:
    name, is_package = module_name(path)
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return SourceModule(path, name, (), f"does not parse ({exc.msg}, line {exc.lineno})")
    return SourceModule(path, name, tuple(import_statements(tree, name, is_package)))


def read_tree() -> dict[str, SourceModule]:
    modules = {}
    for root in SCAN_ROOTS:
        for file in sorted((CORE / root).rglob("*.py")):
            if "__pycache__" in file.parts:
                continue
            path = file.relative_to(CORE).as_posix()
            modules[path] = read_module(path, file.read_text(encoding="utf-8-sig"))
    return modules


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
    return failures


def main() -> int:
    modules = read_tree()
    failures = check(modules)
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        print(f"Import layers: {len(failures)} finding(s). The rules are in this script's docstring; "
              f"a boundary crossed today is named in EXCEPTIONS with its reason.")
        return 1
    print(f"Import layers OK ({len(modules)} modules, {len(CONTRACTS)} contracts, "
          f"{len(EXCEPTIONS)} named exception(s))")
    return 0


def _with_extra_import(module: SourceModule, target: str) -> SourceModule:
    return replace(module, statements=module.statements + (ImportStatement(99999, frozenset({target})),))


def self_test_cases(modules: Mapping[str, SourceModule]) -> dict[str, dict]:
    """Each fake must turn the gate red by the rule it breaks; the real tree, unchanged, must not."""
    def fake(path: str, source: str, expect: str) -> dict:
        return {"modules": {**modules, path: read_module(path, source)}, "expect": expect}

    def listed(module: SourceModule, expect: str) -> dict:
        return {"modules": {**modules, module.path: module}, "expect": expect}

    one = modules["taktik/core/app/ai/comments/generation.py"]
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
    }


def caught(fake: dict) -> bool:
    return any(fake["expect"] in failure for failure in check(fake["modules"]))


def self_test() -> int:
    modules = read_tree()
    cases = self_test_cases(modules)
    missed = [name for name, fake in cases.items() if not caught(fake)]
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
