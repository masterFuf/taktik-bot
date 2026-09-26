"""No schema change outside the numbered list (rule 5 of the anti-drift doctrine).

The bot owns the schema of its tables through the numbered migrations of
`taktik/core/database/local/versions/` (version = `PRAGMA user_version`); the desktop app brings a
base to that version at startup before it opens it. This audit refuses:

1. a numbered list that is not whole: a `mNNNN_*` file the catalog does not name, versions that
   do not run 1..N, or a `schema_manifest.json` that differs from what the catalog produces (a
   released migration edited, or a migration added without
   `python scripts/build_schema_baseline.py --manifest`). The app reads that manifest;
2. DDL (`CREATE TABLE/INDEX/VIEW/TRIGGER`, `ALTER TABLE`, `DROP ...`) in runtime code outside the
   places that may hold it, on both halves when the app sits beside the core:
     - the numbered list itself;
     - the bot's 1.9.8 steps and the app's `schema.ts` / `migrations.ts`, tied to migration 1 by
       `tests/unit/database/test_schema_versions.py` and the app's `npm run schema:baseline`;
     - the app's Turso sync (`electron/sync/`), which writes the REMOTE schema, not the local base.
   Any other file holding DDL is listed in `LISTED` with its count and what removes it. A new
   file, or one more statement in a listed file, fails until it is listed; a listed file holding
   fewer fails too, so the list only shrinks.

DDL is recognised by its upper-case keywords, the way this code base writes SQL. The lazy
`ensure_table` helpers that call the 1.9.8 steps are not seen: they go with those steps.

    python scripts/audit_schema_ownership.py
    python scripts/audit_schema_ownership.py --self-test
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

CORE = Path(__file__).resolve().parents[1]
APP = CORE.parent / "app"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

DDL_RE = re.compile(
    r"\b(?:CREATE\s+(?:UNIQUE\s+|VIRTUAL\s+|TEMP\s+|TEMPORARY\s+)?(?:TABLE|INDEX|VIEW|TRIGGER)"
    r"|ALTER\s+TABLE|DROP\s+(?:TABLE|INDEX|VIEW|TRIGGER))\b"
)
MIGRATION_FILE_RE = re.compile(r"^m\d{4}_")

BOT_ROOTS = ("taktik", "bridges")
APP_ROOTS = ("electron", "src")

#: Where DDL may live, by half: a directory (trailing slash) or a file, and why.
ALLOWED: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "core": (
        ("taktik/core/database/local/versions/", "the numbered list"),
        ("taktik/core/database/local/schemas/", "1.9.8 steps, tied to migration 1 until they retire"),
        ("taktik/core/database/local/migration_steps/", "1.9.8 steps, tied to migration 1 until they retire"),
        ("taktik/core/database/local/schema.py", "orchestrator of the 1.9.8 steps"),
        ("taktik/core/database/local/migrations.py", "orchestrator of the 1.9.8 steps"),
    ),
    "app": (
        ("electron/database/schema.ts", "app tables, and the bot part tied to migration 1 (schema:baseline)"),
        ("electron/database/migrations.ts", "app tables, and the bot part tied to migration 1 (schema:baseline)"),
        ("electron/sync/", "the remote Turso schema, not the local base"),
    ),
}

#: Other files holding DDL: "<half>/<path>" -> (count, what it is, what removes it).
LISTED: Dict[str, Tuple[int, str, str]] = {
    "core/taktik/core/database/repositories/messaging/sent_dm_repository.py": (
        3, "lazy ensure_table of sent_dms (its docstring names the statement once)",
        "the retirement of the 1.9.8 steps and lazy creations (lot L8)",
    ),
    "app/electron/database/repositories/app/sync/TursoLocalSyncRepository.ts": (
        1, "idx_synckey_* unique keys the sync lays on the local base, bot tables included",
        "migration 2 of the bot (lot L6)",
    ),
    "app/electron/database/database-service.ts": (
        2, "header comment naming schema.ts and migrations.ts, no statement", "-",
    ),
}


@dataclass
class Sources:
    """What the audit reads, so a test can hand it other files."""

    files: Dict[str, str]  # "<half>/<relative path>" -> text
    catalog_files: List[str] = field(default_factory=list)  # files the catalog names
    versions_files: List[str] = field(default_factory=list)  # files present in versions/
    catalog_error: Optional[str] = None
    manifest_committed: Optional[str] = None
    manifest_built: Optional[str] = None


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _runtime_files(root: Path, roots: Tuple[str, ...], suffixes: Tuple[str, ...], half: str) -> Dict[str, str]:
    files: Dict[str, str] = {}
    for top in roots:
        base = root / top
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            rel = path.relative_to(root).as_posix()
            if "__pycache__" in rel or "__tests__" in rel or rel.endswith((".test.ts", ".test.tsx", ".d.ts")):
                continue
            files[f"{half}/{rel}"] = _read(path)
    return files


def load_sources(core: Path = CORE, app: Path = APP) -> Sources:
    from taktik.core.database.local.versions.catalog import MIGRATIONS, VERSIONS_DIR, validate_catalog
    from taktik.core.database.local.versions.manifest import MANIFEST_PATH, build_manifest, render_manifest

    files = _runtime_files(core, BOT_ROOTS, (".py",), "core")
    if (app / "electron").is_dir():
        files.update(_runtime_files(app, APP_ROOTS, (".ts", ".tsx"), "app"))

    catalog_error = None
    try:
        validate_catalog(MIGRATIONS)
    except ValueError as exc:
        catalog_error = str(exc)
    named = [name for m in MIGRATIONS for name in (m.sql_file, m.retired_tables_file) if name]
    present = sorted(p.name for p in VERSIONS_DIR.iterdir() if p.is_file() and MIGRATION_FILE_RE.match(p.name))
    built = None if catalog_error else render_manifest(build_manifest(MIGRATIONS))
    committed = _read(MANIFEST_PATH).replace("\r\n", "\n") if MANIFEST_PATH.exists() else None
    return Sources(files=files, catalog_files=named, versions_files=present, catalog_error=catalog_error,
                   manifest_committed=committed, manifest_built=built)


def check_numbered_list(sources: Sources) -> List[str]:
    findings: List[str] = []
    if sources.catalog_error:
        findings.append(f"numbered list: {sources.catalog_error}")
    for name in sources.versions_files:
        if name not in sources.catalog_files:
            findings.append(f"numbered list: versions/{name} is not in the catalog (catalog.py MIGRATIONS)")
    for name in sources.catalog_files:
        if name not in sources.versions_files:
            findings.append(f"numbered list: the catalog names versions/{name}, which does not exist")
    if sources.manifest_committed is None:
        findings.append("numbered list: versions/schema_manifest.json is missing (the app reads it)")
    elif sources.manifest_built is not None and sources.manifest_committed != sources.manifest_built:
        findings.append(
            "numbered list: schema_manifest.json differs from the catalog: a released migration was edited, "
            "or the manifest was not rebuilt (python scripts/build_schema_baseline.py --manifest)"
        )
    return findings


def _allowed(key: str, allowed: Mapping[str, Tuple[Tuple[str, str], ...]]) -> bool:
    half, _, rel = key.partition("/")
    for prefix, _why in allowed.get(half, ()):
        if rel == prefix or (prefix.endswith("/") and rel.startswith(prefix)):
            return True
    return False


def ddl_counts(files: Mapping[str, str], allowed: Mapping[str, Tuple[Tuple[str, str], ...]] = ALLOWED) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for key, text in files.items():
        if _allowed(key, allowed):
            continue
        found = len(DDL_RE.findall(text))
        if found:
            counts[key] = found
    return counts


def check_ddl(sources: Sources, listed: Mapping[str, Tuple[int, str, str]] = LISTED,
              allowed: Mapping[str, Tuple[Tuple[str, str], ...]] = ALLOWED) -> List[str]:
    findings: List[str] = []
    counts = ddl_counts(sources.files, allowed)
    has_app = any(key.startswith("app/") for key in sources.files)
    for key, found in sorted(counts.items()):
        declared = listed.get(key)
        if declared is None:
            findings.append(
                f"schema change outside the numbered list: {key} holds {found} DDL statement(s); "
                "a bot table changes through a numbered migration (versions/), an app table in migrations.ts"
            )
        elif found > declared[0]:
            findings.append(f"schema change outside the numbered list: {key} holds {found} DDL statement(s), {declared[0]} listed")
    for key, (count, _what, _removal) in sorted(listed.items()):
        if key.startswith("app/") and not has_app:
            continue
        found = counts.get(key, 0)
        if found < count:
            findings.append(f"stale entry: {key} is listed with {count} DDL statement(s) and holds {found}: lower it in LISTED")
    return findings


def audit(sources: Sources) -> List[str]:
    return check_numbered_list(sources) + check_ddl(sources)


def self_test() -> List[str]:
    """The audit still turns red on what it guards against."""
    clean = Sources(
        files={
            "core/taktik/core/database/local/versions/m0001_baseline.sql": "",
            "core/taktik/core/database/local/schemas/x.py": "CREATE TABLE IF NOT EXISTS a (id)",
            "core/taktik/core/x.py": "print('no schema here')",
            "app/electron/database/migrations.ts": "db.exec('ALTER TABLE accounts ADD COLUMN x')",
            "app/electron/sync/schema/remote.ts": "'CREATE TABLE IF NOT EXISTS remote_x (id)'",
        },
        catalog_files=["m0001_baseline.sql"],
        versions_files=["m0001_baseline.sql"],
        manifest_committed="{}\n",
        manifest_built="{}\n",
    )
    listed = {"app/electron/l.ts": (1, "listed", "test")}
    clean.files["app/electron/l.ts"] = "db.exec(`CREATE UNIQUE INDEX IF NOT EXISTS k ON t(c)`)"

    def variant(**changes) -> Sources:
        files = {**clean.files, **changes.pop("files", {})}
        return Sources(**{**clean.__dict__, "files": files, **changes})

    cases = {
        "clean tree": (clean, False),
        "DDL in a bot repository": (variant(files={"core/taktik/core/database/repositories/r.py": "ALTER TABLE accounts ADD COLUMN y"}), True),
        "DDL in an app service": (variant(files={"app/electron/services/s.ts": "db.exec('CREATE INDEX i ON interactions(x)')"}), True),
        "one more statement in a listed file": (variant(files={"app/electron/l.ts": "CREATE INDEX a ON t(c); DROP INDEX b"}), True),
        "a listed file that holds fewer": (variant(files={"app/electron/l.ts": "no statement"}), True),
        "a migration file outside the catalog": (variant(versions_files=["m0001_baseline.sql", "m0002_extra.sql"]), True),
        "an edited migration": (variant(manifest_built='{"changed": true}\n'), True),
        "a gap in the catalog": (variant(catalog_error="migration versions must run 1..N without gaps"), True),
    }
    failures = []
    for name, (sources, should_fail) in cases.items():
        found = check_numbered_list(sources) + check_ddl(sources, listed=listed)
        if bool(found) != should_fail:
            failures.append(f"{name}: expected {'a finding' if should_fail else 'none'}, got {found}")
    return failures


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        failures = self_test()
        if failures:
            print(f"Schema ownership self-test: {len(failures)} failure(s)")
            for failure in failures:
                print(f" - {failure}")
            return 1
        print("Schema ownership self-test OK (DDL outside the list, stale entry, edited migration, file outside the catalog)")
        return 0
    sources = load_sources()
    findings = audit(sources)
    if findings:
        print(f"Schema ownership: {len(findings)} finding(s)")
        for finding in findings:
            print(f" - {finding}")
        return 1
    halves = "bot and app" if any(k.startswith("app/") for k in sources.files) else "bot only (no app beside the core)"
    print(
        f"Schema ownership OK: numbered list whole ({len(sources.catalog_files)} file(s), manifest up to date), "
        f"no DDL outside it ({halves}, {len(LISTED)} listed file(s))"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
