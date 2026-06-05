"""Audit SQLite table coverage across source schemas and GitBook docs.

This script is intentionally read-only. It compares table names declared in
Python/Electron SQLite sources with the documented table sections in
``taktik-docs/bot/database/schema.md``.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SOURCE_FILES = [
    ROOT / "bot" / "taktik" / "core" / "database" / "local" / "schema.py",
    ROOT / "bot" / "taktik" / "core" / "database" / "local" / "migrations.py",
    ROOT / "bot" / "taktik" / "core" / "database" / "local" / "schemas" / "enrichment.py",
    ROOT / "bot" / "taktik" / "core" / "database" / "local" / "schemas" / "gmail.py",
    ROOT / "bot" / "taktik" / "core" / "database" / "local" / "schemas" / "instagram.py",
    ROOT / "bot" / "taktik" / "core" / "database" / "local" / "schemas" / "scraping.py",
    ROOT / "bot" / "taktik" / "core" / "database" / "local" / "schemas" / "social_graph.py",
    ROOT / "bot" / "taktik" / "core" / "database" / "local" / "schemas" / "tiktok.py",
    ROOT / "bot" / "taktik" / "core" / "database" / "local" / "migration_steps" / "scraping.py",
    ROOT / "bot" / "taktik" / "core" / "database" / "local" / "migration_steps" / "enrichment.py",
    ROOT / "bot" / "taktik" / "core" / "database" / "local" / "migration_steps" / "tiktok.py",
    ROOT / "front" / "electron" / "database" / "schema.sql",
    ROOT / "front" / "electron" / "database" / "schema.ts",
    ROOT / "front" / "electron" / "database" / "migrations.ts",
    ROOT / "front" / "electron" / "database" / "repositories" / "platforms" / "instagram" / "scraping" / "ScrapedProfileRepository.ts",
]

DOC_SCHEMA_PATH = ROOT / "taktik-docs" / "bot" / "database" / "schema.md"

# Migration scratch tables are implementation details, not persistent domain
# tables that should be documented as part of the application schema.
IGNORED_TABLES = {
    "_tiktok_scraped_profiles_backup",
}

CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(?P<table>[A-Za-z_][A-Za-z0-9_]*)[`\"']?\s*\(",
    re.IGNORECASE,
)
DOC_TABLE_RE = re.compile(r"^###\s+`(?P<table>[A-Za-z_][A-Za-z0-9_]*)`", re.MULTILINE)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def source_tables() -> dict[str, set[str]]:
    tables_by_file: dict[str, set[str]] = {}
    for path in SOURCE_FILES:
        if not path.exists():
            raise FileNotFoundError(path)
        tables = {
            match.group("table")
            for match in CREATE_TABLE_RE.finditer(read(path))
            if match.group("table") not in IGNORED_TABLES
        }
        if tables:
            tables_by_file[str(path.relative_to(ROOT))] = tables
    return tables_by_file


def documented_tables() -> set[str]:
    if not DOC_SCHEMA_PATH.exists():
        raise FileNotFoundError(DOC_SCHEMA_PATH)
    return {match.group("table") for match in DOC_TABLE_RE.finditer(read(DOC_SCHEMA_PATH))}


def main() -> int:
    by_file = source_tables()
    source = set().union(*by_file.values()) if by_file else set()
    documented = documented_tables()

    missing = sorted(source - documented)
    stale = sorted(documented - source)

    if missing or stale:
        print("SQLite schema documentation audit failed:")
        if missing:
            print(" - Missing from taktik-docs/bot/database/schema.md:")
            for table in missing:
                owners = sorted(file for file, tables in by_file.items() if table in tables)
                print(f"   - {table} ({', '.join(owners)})")
        if stale:
            print(" - Documented but not found in scanned schema sources:")
            for table in stale:
                print(f"   - {table}")
        return 1

    print(f"SQLite schema docs OK ({len(source)} tables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
