"""Numbered schema migrations of the local SQLite database (version = PRAGMA user_version)."""

from .catalog import MIGRATIONS, Migration, schema_version
from .runner import (
    ABSENT,
    BEHIND,
    CURRENT,
    EMPTY,
    LEGACY_RECOGNIZED,
    LEGACY_UNRECOGNIZED,
    TOO_NEW,
    MigrationResult,
    SchemaStatus,
    inspect_database,
    migrate_database,
)

__all__ = [
    "ABSENT",
    "BEHIND",
    "CURRENT",
    "EMPTY",
    "LEGACY_RECOGNIZED",
    "LEGACY_UNRECOGNIZED",
    "MIGRATIONS",
    "Migration",
    "MigrationResult",
    "SchemaStatus",
    "TOO_NEW",
    "inspect_database",
    "migrate_database",
    "schema_version",
]
