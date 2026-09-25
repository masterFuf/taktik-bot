"""Automatic backup taken before any schema migration, and read-only access to a base.

A backup is a consistent copy made by SQLite's backup API from a read-only connection, checked
with `quick_check` and counted table by table before it is trusted. Only the automatic backups
of `backups/` are ever pruned; any other file is left alone.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .fingerprint import quote_identifier

AUTO_BACKUP_PATTERN = re.compile(r"^taktik-data\.v(\d+)-v(\d+)\.(\d{8})-(\d+)\.db$")
KEEP_AUTO_BACKUPS = 2
FREE_SPACE_FACTOR = 1.2
_SIDE_FILES = ("-wal", "-shm", "-journal")


class BackupRefused(RuntimeError):
    """The backup could not be made or verified; nothing was migrated."""


@dataclass
class BackupReport:
    path: str
    size_bytes: int
    seconds: float
    quick_check: str
    row_counts: Dict[str, int] = field(default_factory=dict)
    from_version: int = 0
    to_version: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


def connect_read_only(db_path, allow_immutable: bool = True) -> sqlite3.Connection:
    """Open without writing anything, side files included.

    A closed WAL base has no -wal/-shm: a plain read-only open would create them. It is then
    opened immutable, which is safe because nobody holds it open. A caller about to open the
    base for writing anyway passes `allow_immutable=False`.
    """
    path = Path(db_path).resolve()
    uri = path.as_uri() + "?mode=ro"
    if allow_immutable and not any(Path(str(path) + suffix).exists() for suffix in _SIDE_FILES):
        uri += "&immutable=1"
    return sqlite3.connect(uri, uri=True, timeout=30.0)


def database_size(db_path) -> int:
    path = Path(db_path)
    wal = Path(str(path) + "-wal")
    return path.stat().st_size + (wal.stat().st_size if wal.exists() else 0)


def default_backup_dir(db_path) -> Path:
    return Path(db_path).resolve().parent / "backups"


def row_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    """Rows per real table (virtual tables are counted through their shadow tables)."""
    counts: Dict[str, int] = {}
    for name, sql in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY name"
    ):
        if sql and sql.lstrip().upper().startswith("CREATE VIRTUAL TABLE"):
            continue
        counts[name] = conn.execute(f"SELECT COUNT(*) FROM {quote_identifier(name)}").fetchone()[0]
    return counts


def quick_check(conn: sqlite3.Connection) -> str:
    rows = conn.execute("PRAGMA quick_check").fetchall()
    return "ok" if rows == [("ok",)] else "; ".join(str(r[0]) for r in rows[:5])


def copy_database(source_path, target_path) -> None:
    """Consistent single-file copy (one backup step = one read snapshot)."""
    source = connect_read_only(source_path)
    target = sqlite3.connect(str(target_path))
    try:
        source.backup(target, pages=-1)
        target.execute("PRAGMA journal_mode=DELETE")
    finally:
        target.close()
        source.close()


def remove_database_file(path) -> None:
    for suffix in ("",) + _SIDE_FILES:
        candidate = Path(str(path) + suffix)
        if candidate.exists():
            candidate.unlink()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _target_path(backup_dir: Path, from_version: int, to_version: int, day: str) -> Path:
    """`taktik-data.v<from>-v<to>.<date>-<n>.db`: n orders the backups of one day."""
    taken = [
        int(match.group(4))
        for match in (AUTO_BACKUP_PATTERN.match(p.name.replace(".partial", "")) for p in backup_dir.iterdir())
        if match and match.group(3) == day
    ]
    return backup_dir / f"taktik-data.v{from_version}-v{to_version}.{day}-{max(taken, default=0) + 1}.db"


def create_backup(
    db_path,
    backup_dir,
    from_version: int,
    to_version: int,
    *,
    rehearsal: bool = False,
    clock: Optional[Callable[[], datetime]] = None,
) -> BackupReport:
    """Copy, check and count the base. Refuses, without writing, when the disk is too full."""
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    needed = int(database_size(db_path) * FREE_SPACE_FACTOR * (2 if rehearsal else 1))
    free = shutil.disk_usage(backup_dir).free
    if free < needed:
        raise BackupRefused(f"not enough free space in {backup_dir}: {free} bytes free, {needed} needed")

    day = (clock or _utc_now)().strftime("%Y%m%d")
    target = _target_path(backup_dir, from_version, to_version, day)
    partial = target.with_name(target.name + ".partial")
    remove_database_file(partial)
    started = time.monotonic()
    try:
        copy_database(db_path, partial)
        conn = sqlite3.connect(str(partial))
        try:
            check = quick_check(conn)
            counts = row_counts(conn)
        finally:
            conn.close()
        if check != "ok":
            raise BackupRefused(f"backup failed quick_check: {check}")
        os.replace(partial, target)
    finally:
        remove_database_file(partial)

    report = BackupReport(
        path=str(target),
        size_bytes=target.stat().st_size,
        seconds=round(time.monotonic() - started, 2),
        quick_check=check,
        row_counts=counts,
        from_version=from_version,
        to_version=to_version,
    )
    sidecar = target.with_name(target.name + ".json")
    sidecar.write_text(json.dumps(report.to_dict(), indent=1, sort_keys=True), encoding="utf-8", newline="")
    return report


def prune_auto_backups(backup_dir, keep: int = KEEP_AUTO_BACKUPS) -> List[str]:
    """Delete automatic backups beyond the `keep` newest. Other files are never touched."""
    backup_dir = Path(backup_dir)
    if not backup_dir.is_dir():
        return []
    found = []
    for entry in backup_dir.iterdir():
        match = AUTO_BACKUP_PATTERN.match(entry.name)
        if match and entry.is_file():
            found.append((match.group(3), int(match.group(4)), entry))
    found.sort(key=lambda item: (item[0], item[1]), reverse=True)
    removed = []
    for _day, _seq, entry in found[keep:]:
        entry.unlink()
        sidecar = entry.with_name(entry.name + ".json")
        if sidecar.exists():
            sidecar.unlink()
        removed.append(entry.name)
    return removed


__all__ = [
    "AUTO_BACKUP_PATTERN",
    "BackupRefused",
    "BackupReport",
    "KEEP_AUTO_BACKUPS",
    "connect_read_only",
    "copy_database",
    "create_backup",
    "database_size",
    "default_backup_dir",
    "prune_auto_backups",
    "quick_check",
    "remove_database_file",
    "row_counts",
]
