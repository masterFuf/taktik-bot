"""Helpers shared by SQLite migration steps."""

from __future__ import annotations

import re


_IDENTIFIER_RE = re.compile(r'^[a-z][a-z0-9_]*$')


def _validate_sql_identifier(name: str) -> str:
    """Assert that *name* is a safe SQL identifier."""
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Unsafe SQL identifier rejected: {name!r}")
    return name
