"""Bring the bot's part of a local database to this build's schema version, or say why not.

`inspect_database` never writes. `migrate_database` backs the base up first, applies the pending
numbered migrations in one transaction, checks the result against the catalog before committing,
and stamps a recognised 1.9.8 base without rewriting any of its tables. The desktop app's objects
are never compared, and a migration that creates, changes or drops one is rolled back.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from loguru import logger

from .backup import (
    BackupRefused,
    BackupReport,
    connect_read_only,
    copy_database,
    create_backup,
    default_backup_dir,
    prune_auto_backups,
    quick_check,
    remove_database_file,
    row_counts,
)
from .catalog import BASELINE, MIGRATIONS, REBUILD, Migration, schema_version
from .fingerprint import compare, fingerprint, scope
from .journal import APPLIED, JOURNAL_TABLE, STAMPED, ensure_journal, read_journal, record_migration
from .legacy import run_bot_legacy_steps

ABSENT = "absent"
EMPTY = "empty"
CURRENT = "current"
BEHIND = "behind"
TOO_NEW = "too_new"
LEGACY_RECOGNIZED = "legacy_recognized"
LEGACY_UNRECOGNIZED = "legacy_unrecognized"

ProgressCallback = Callable[[str, str], None]

_fingerprint_cache: Dict[Tuple[str, Tuple[Migration, ...]], Dict] = {}


class MigrationFailed(RuntimeError):
    def __init__(self, message: str, differences: Optional[List[str]] = None,
                 backup: Optional[BackupReport] = None):
        super().__init__(message)
        self.differences = differences or []
        self.backup = backup


@dataclass
class SchemaStatus:
    db_path: str
    state: str
    user_version: Optional[int]
    target_version: int
    differences: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class MigrationResult:
    success: bool
    action: str
    db_path: str
    from_version: Optional[int]
    to_version: int
    message: str = ""
    applied: List[int] = field(default_factory=list)
    differences: List[str] = field(default_factory=list)
    backup: Optional[Dict] = None
    legacy_steps_ran: bool = False
    seconds: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


def _schema_of(kind: str, catalog: Sequence[Migration]) -> Dict:
    """The bot's definition after migration 1 (`baseline`) or after all of them (`target`).

    Built in memory from the catalog alone, so everything in it is the bot's.
    """
    key = (kind, tuple(catalog))
    if key not in _fingerprint_cache:
        conn = sqlite3.connect(":memory:", isolation_level=None)
        try:
            conn.execute("BEGIN")
            if kind == "target":
                ensure_journal(conn)
                steps = list(catalog)
            else:
                steps = [catalog[0]]
            for migration in steps:
                migration.run(conn)
            conn.execute("COMMIT")
            fp = fingerprint(conn)
        finally:
            conn.close()
        retired = {name for m in steps for name in m.retired_tables()}
        _fingerprint_cache[key] = scope(fp, fp["tables"], fp["views"], fp["triggers"], retired - set(fp["tables"]))
    return _fingerprint_cache[key]


def baseline_fingerprint(catalog: Sequence[Migration] = MIGRATIONS) -> Dict:
    """The bot's part of a base the 1.9.8 app and bot left behind (migration 1, no journal)."""
    return _schema_of("baseline", catalog)


def target_fingerprint(catalog: Sequence[Migration] = MIGRATIONS) -> Dict:
    """The bot's part of a base at the catalog's last version."""
    return _schema_of("target", catalog)


@dataclass(frozen=True)
class _Owned:
    tables: frozenset
    views: frozenset
    triggers: frozenset


def _owned(catalog: Sequence[Migration]) -> _Owned:
    """Everything the bot may create, change or drop, at any version of the catalog."""
    base, target = baseline_fingerprint(catalog), target_fingerprint(catalog)
    return _Owned(
        tables=frozenset(set(base["tables"]) | set(target["tables"]) | set(base["retired_tables"])
                         | set(target["retired_tables"]) | {JOURNAL_TABLE}),
        views=frozenset(set(base["views"]) | set(target["views"])),
        triggers=frozenset(set(base["triggers"]) | set(target["triggers"])),
    )


def foreign_objects(conn: sqlite3.Connection, owned: _Owned) -> Dict[Tuple[str, str], Tuple[str, str]]:
    """Every schema object the bot does not own: the desktop app's tables, views, triggers
    (those on the bot's tables included) and their indexes."""
    out = {}
    for typ, name, tbl_name, sql in conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite\\_%' ESCAPE '\\'"
    ):
        if typ == "table" and name in owned.tables:
            continue
        if typ == "view" and name in owned.views:
            continue
        if typ == "trigger" and name in owned.triggers:
            continue
        if typ == "index" and tbl_name in owned.tables:
            continue
        out[(typ, name)] = (tbl_name, sql)
    return out


def _foreign_changes(before: Dict, after: Dict) -> List[str]:
    changes = [f"{typ} {name} removed" for typ, name in sorted(set(before) - set(after))]
    changes += [f"{typ} {name} created" for typ, name in sorted(set(after) - set(before))]
    changes += [f"{typ} {name} changed" for typ, name in sorted(set(before) & set(after))
                if before[(typ, name)] != after[(typ, name)]]
    return changes


def _object_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite\\_%' ESCAPE '\\'"
    ).fetchone()[0]


def inspect_database(db_path, catalog: Sequence[Migration] = MIGRATIONS, *,
                     leave_no_side_file: bool = True) -> SchemaStatus:
    """Where the bot's part of the base stands against the catalog. Never writes, never creates
    the file. `leave_no_side_file=False` allows the -wal/-shm files any reader of a WAL base
    creates (the bot's own opening), instead of an immutable open."""
    target = schema_version(catalog)
    path = Path(db_path)
    if not path.exists():
        return SchemaStatus(str(path), ABSENT, None, target)
    conn = connect_read_only(path, allow_immutable=leave_no_side_file)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0 and _object_count(conn) == 0:
            return SchemaStatus(str(path), EMPTY, 0, target)
        if version > target:
            return SchemaStatus(str(path), TOO_NEW, version, target)
        if version == 0:
            diffs = compare(baseline_fingerprint(catalog), fingerprint(conn))
            state = LEGACY_UNRECOGNIZED if diffs else LEGACY_RECOGNIZED
            return SchemaStatus(str(path), state, 0, target, differences=diffs)
        if version < target:
            return SchemaStatus(str(path), BEHIND, version, target)
        status = SchemaStatus(str(path), CURRENT, version, target)
        journal = {row["version"]: row for row in read_journal(conn)}
        for migration in catalog:
            row = journal.get(migration.version)
            if row is None:
                status.warnings.append(f"journal has no row for migration {migration.version}")
            elif row["checksum"] != migration.checksum():
                status.warnings.append(f"migration {migration.version} changed since it was applied")
        status.differences = compare(target_fingerprint(catalog), fingerprint(conn))
        if status.differences:
            status.warnings.append(f"schema differs from version {target} ({len(status.differences)} differences)")
        return status
    finally:
        conn.close()


def _run_pending(conn, pending: Sequence[Migration], *, stamp_baseline: bool,
                 applied_by: str, backup_path: Optional[str]) -> List[int]:
    ensure_journal(conn)
    applied = []
    for migration in pending:
        started = time.monotonic()
        if migration.kind == BASELINE and stamp_baseline:
            mode = STAMPED
        else:
            migration.run(conn)
            mode = APPLIED
            applied.append(migration.version)
        record_migration(conn, migration, mode, applied_by, backup_path,
                         int((time.monotonic() - started) * 1000))
    return applied


def _foreign_key_violations(conn) -> set:
    return {tuple(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()}


def _rehearse(backup: BackupReport, pending, catalog, from_version: int, applied_by: str) -> None:
    rehearsal_path = Path(backup.path).with_name(Path(backup.path).stem + ".rehearsal.db")
    remove_database_file(rehearsal_path)
    problems: List[str] = []
    try:
        copy_database(backup.path, rehearsal_path)
        conn = sqlite3.connect(str(rehearsal_path), isolation_level=None)
        try:
            owned = _owned(catalog)
            conn.execute("PRAGMA foreign_keys=OFF")
            before_fk = _foreign_key_violations(conn)
            conn.execute("BEGIN IMMEDIATE")
            before_foreign = foreign_objects(conn, owned)
            _run_pending(conn, pending, stamp_baseline=from_version == 0,
                         applied_by=applied_by, backup_path=backup.path)
            new_fk = _foreign_key_violations(conn) - before_fk
            problems += [f"new foreign key violation {row}" for row in sorted(new_fk)[:20]]
            problems += [f"not the bot's: {c}" for c in _foreign_changes(before_foreign, foreign_objects(conn, owned))]
            conn.execute("COMMIT")
            problems += compare(target_fingerprint(catalog), fingerprint(conn))
            check = quick_check(conn)
            if check != "ok":
                problems.append(f"quick_check: {check}")
            if all(m.rows_unchanged for m in pending):
                after = row_counts(conn)
                for table, count in backup.row_counts.items():
                    if table == JOURNAL_TABLE:
                        continue
                    if table not in after:
                        if count:
                            problems.append(f"table {table} lost with {count} rows")
                    elif after[table] != count:
                        problems.append(f"rows of {table}: {count} -> {after[table]}")
        finally:
            conn.close()
    except MigrationFailed:
        raise
    except Exception as exc:
        problems.append(f"{type(exc).__name__}: {exc}")
    finally:
        remove_database_file(rehearsal_path)
    if problems:
        raise MigrationFailed("rehearsal on a copy of the backup failed; the base was not touched",
                              problems, backup)


def _apply(db_path, catalog, from_version: int, backup: Optional[BackupReport], backup_dir: Path,
           applied_by: str, progress: ProgressCallback, clock) -> Tuple[List[int], BackupReport]:
    target = schema_version(catalog)
    pending = [m for m in catalog if m.version > from_version]
    rehearse = any(m.kind == REBUILD for m in pending)
    stamp_only = all(m.kind == BASELINE for m in pending) and from_version == 0
    conn = sqlite3.connect(str(db_path), timeout=30.0, isolation_level=None)
    try:
        if rehearse:
            conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN IMMEDIATE")
        try:
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            if current != from_version:
                raise MigrationFailed(f"the base moved to version {current} while waiting for the lock")
            if backup is None:
                progress("backup", f"backing up before version {from_version} -> {target}")
                backup = create_backup(db_path, backup_dir, from_version, target,
                                       rehearsal=rehearse, clock=clock)
            if rehearse:
                progress("rehearsal", "rehearsing the rebuild on a copy of the backup")
                _rehearse(backup, pending, catalog, from_version, applied_by)
            before_fk = set() if stamp_only else _foreign_key_violations(conn)
            owned = _owned(catalog)
            before_foreign = foreign_objects(conn, owned)
            progress("apply", f"applying {len(pending)} migration(s)")
            applied = _run_pending(conn, pending, stamp_baseline=from_version == 0,
                                   applied_by=applied_by, backup_path=backup.path)
            progress("verify", "checking the schema before committing")
            touched = _foreign_changes(before_foreign, foreign_objects(conn, owned))
            if touched:
                raise MigrationFailed("the migration touched objects the bot does not own", touched)
            if not stamp_only:
                new_fk = _foreign_key_violations(conn) - before_fk
                if new_fk:
                    raise MigrationFailed("the migration broke foreign keys",
                                          [f"new foreign key violation {row}" for row in sorted(new_fk)[:20]])
            diffs = compare(target_fingerprint(catalog), fingerprint(conn))
            if diffs:
                raise MigrationFailed(f"the schema after migration is not version {target}", diffs)
            conn.execute(f"PRAGMA user_version = {int(target)}")
            conn.execute("COMMIT")
        except BaseException as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            if isinstance(exc, MigrationFailed):
                if exc.backup is None:
                    exc.backup = backup
                raise
            if isinstance(exc, Exception) and not isinstance(exc, BackupRefused):
                raise MigrationFailed(f"{type(exc).__name__}: {exc}", backup=backup) from exc
            raise
    finally:
        conn.close()
    return applied, backup


def _create(db_path, catalog, applied_by: str) -> List[int]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    target = schema_version(catalog)
    conn = sqlite3.connect(str(path), timeout=30.0, isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("BEGIN IMMEDIATE")
        try:
            if conn.execute("PRAGMA user_version").fetchone()[0] != 0 or _object_count(conn):
                raise MigrationFailed("the base stopped being empty while waiting for the lock")
            applied = _run_pending(conn, list(catalog), stamp_baseline=False,
                                   applied_by=applied_by, backup_path=None)
            diffs = compare(target_fingerprint(catalog), fingerprint(conn))
            if diffs:
                raise MigrationFailed(f"a new base does not come out at version {target}", diffs)
            conn.execute(f"PRAGMA user_version = {int(target)}")
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return applied


def migrate_database(
    db_path,
    *,
    backup_dir=None,
    catalog: Sequence[Migration] = MIGRATIONS,
    applied_by: str = "core",
    on_progress: Optional[ProgressCallback] = None,
    legacy_steps: Optional[Callable[[str], None]] = None,
    clock: Optional[Callable[[], datetime]] = None,
    legacy_app_done: bool = False,
) -> MigrationResult:
    """Bring the base to the catalog's version. A base newer than the catalog is never written.

    A version-0 base that is not the 1.9.8 schema is first handed back to the 1.9.8 app
    (`needs_legacy_app`): the bot's own old steps crash on bases the app has not migrated yet,
    as in 1.9.8 where the app always opened the base first. Once the app has run
    (`legacy_app_done`), the bot's steps run, then the base is inspected again.
    """
    started = time.monotonic()
    progress = on_progress or (lambda step, message="": None)
    before = inspect_database(db_path, catalog)
    target = before.target_version
    legacy_ran = False

    def done(success: bool, action: str, message: str, *, applied=None, differences=None,
             backup: Optional[BackupReport] = None) -> MigrationResult:
        result = MigrationResult(
            success=success, action=action, db_path=str(db_path), from_version=before.user_version,
            to_version=target if success else (before.user_version or 0), message=message,
            applied=applied or [], differences=differences or [],
            backup=backup.to_dict() if backup else None, legacy_steps_ran=legacy_ran,
            seconds=round(time.monotonic() - started, 2),
        )
        log = logger.info if success else logger.warning
        log(f"schema {action}: {message}")
        return result

    if before.state == CURRENT:
        return done(True, "none", f"already at version {target}")
    if before.state == TOO_NEW:
        return done(False, "refused",
                    f"the base is at version {before.user_version}, this build knows up to {target}")

    backup: Optional[BackupReport] = None
    try:
        if before.state in (ABSENT, EMPTY):
            progress("create", f"creating a new base at version {target}")
            applied = _create(db_path, catalog, applied_by)
            return done(True, "created", f"new base created at version {target}", applied=applied)

        backup_root = Path(backup_dir) if backup_dir else default_backup_dir(db_path)
        from_version = before.user_version or 0
        if before.state == LEGACY_UNRECOGNIZED:
            progress("backup", f"backing up before version 0 -> {target}")
            backup = create_backup(db_path, backup_root, 0, target, clock=clock)
            if not legacy_app_done:
                prune_auto_backups(backup_root)
                return done(False, "needs_legacy_app",
                            "the base is not the 1.9.8 schema: the 1.9.8 app must migrate it first",
                            differences=before.differences, backup=backup)
            progress("legacy_steps", "running the bot's own 1.9.8 steps after the app's")
            try:
                (legacy_steps or run_bot_legacy_steps)(str(db_path))
            except Exception as exc:
                prune_auto_backups(backup_root)
                return done(False, "failed", f"the bot's 1.9.8 steps failed: {type(exc).__name__}: {exc}",
                            backup=backup)
            legacy_ran = True
            again = inspect_database(db_path, catalog)
            if again.state != LEGACY_RECOGNIZED:
                prune_auto_backups(backup_root)
                return done(False, "needs_legacy_app",
                            "the base is not the 1.9.8 schema even after the bot's steps: "
                            "the 1.9.8 app must open it once more", differences=again.differences,
                            backup=backup)

        applied, backup = _apply(db_path, catalog, from_version, backup, backup_root,
                                 applied_by, progress, clock)
        prune_auto_backups(backup_root)
        action = "stamped" if from_version == 0 else "migrated"
        return done(True, action, f"version {from_version} -> {target}", applied=applied, backup=backup)
    except BackupRefused as exc:
        return done(False, "refused", str(exc), backup=backup)
    except MigrationFailed as exc:
        return done(False, "failed", str(exc), differences=exc.differences, backup=exc.backup or backup)
    except Exception as exc:
        return done(False, "failed", f"{type(exc).__name__}: {exc}", backup=backup)


__all__ = [
    "ABSENT",
    "BEHIND",
    "CURRENT",
    "EMPTY",
    "LEGACY_RECOGNIZED",
    "LEGACY_UNRECOGNIZED",
    "MigrationFailed",
    "MigrationResult",
    "SchemaStatus",
    "TOO_NEW",
    "baseline_fingerprint",
    "foreign_objects",
    "inspect_database",
    "migrate_database",
    "target_fingerprint",
]
