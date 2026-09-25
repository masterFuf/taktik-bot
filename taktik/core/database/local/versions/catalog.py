"""The numbered list of schema migrations of the local database.

Version N of a base is `PRAGMA user_version`, and it describes the bot's objects only: the
desktop app keeps creating and changing its own tables. Migration 1 is the baseline: the bot's
part of the 1.9.8 schema, applied to a new base and only stamped on an existing one. Every later
change is a new entry here, never an edit of a released one.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple

from .sql_text import split_statements

BASELINE = "baseline"
ADDITIVE = "additive"
REBUILD = "rebuild"
KINDS = (BASELINE, ADDITIVE, REBUILD)

VERSIONS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Migration:
    """One numbered step. `rebuild` steps are rehearsed on a copy before touching the base."""

    version: int
    name: str
    kind: str
    sql_file: Optional[str] = None
    apply_fn: Optional[Callable[[sqlite3.Connection], None]] = None
    rows_unchanged: bool = True
    retired_tables_file: Optional[str] = None

    def sql(self) -> str:
        if not self.sql_file:
            return ""
        return (VERSIONS_DIR / self.sql_file).read_text(encoding="utf-8").replace("\r\n", "\n")

    def retired_tables(self) -> Tuple[str, ...]:
        """Tables this step retires: a base that still has one is not at this version."""
        if not self.retired_tables_file:
            return ()
        return tuple(json.loads((VERSIONS_DIR / self.retired_tables_file).read_text(encoding="utf-8")))

    def checksum(self) -> str:
        if self.sql_file:
            payload = self.sql()
            if self.retired_tables_file:
                payload += "\n-- retired tables: " + ",".join(self.retired_tables())
        else:
            payload = f"python:{self.version}:{self.name}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def run(self, conn: sqlite3.Connection) -> None:
        """Execute inside the caller's transaction."""
        if self.sql_file:
            for statement in split_statements(self.sql()):
                conn.execute(statement)
        elif self.apply_fn is not None:
            self.apply_fn(conn)
        else:
            raise ValueError(f"migration {self.version} has neither SQL nor function")


MIGRATIONS: Sequence[Migration] = (
    Migration(1, "baseline", BASELINE, sql_file="m0001_baseline.sql",
              retired_tables_file="m0001_retired_tables.json"),
)


def validate_catalog(catalog: Sequence[Migration]) -> None:
    if not catalog:
        raise ValueError("empty migration catalog")
    for index, migration in enumerate(catalog, start=1):
        if migration.version != index:
            raise ValueError(f"migration versions must run 1..N without gaps (found {migration.version} at {index})")
        if migration.kind not in KINDS:
            raise ValueError(f"migration {migration.version}: unknown kind {migration.kind!r}")
        if (migration.kind == BASELINE) != (index == 1):
            raise ValueError("the baseline must be migration 1, and only it")


def schema_version(catalog: Sequence[Migration] = MIGRATIONS) -> int:
    validate_catalog(catalog)
    return catalog[-1].version


__all__ = [
    "ADDITIVE",
    "BASELINE",
    "MIGRATIONS",
    "Migration",
    "REBUILD",
    "VERSIONS_DIR",
    "schema_version",
    "validate_catalog",
]
