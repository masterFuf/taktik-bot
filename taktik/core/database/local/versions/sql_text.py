"""SQL text helpers for the numbered schema migrations."""

from __future__ import annotations

import sqlite3
from typing import List

_QUOTES = ("'", '"', "`")


def strip_comments(sql: str) -> str:
    """Remove `--` and `/* */` comments outside quoted text, then trailing spaces and blank lines."""
    out: List[str] = []
    i, n = 0, len(sql)
    quote = None
    while i < n:
        ch = sql[i]
        if quote:
            out.append(ch)
            if ch == quote:
                if i + 1 < n and sql[i + 1] == quote:
                    out.append(sql[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in _QUOTES:
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "[":
            end = sql.find("]", i)
            end = n - 1 if end < 0 else end
            out.append(sql[i:end + 1])
            i = end + 1
            continue
        if sql.startswith("--", i):
            end = sql.find("\n", i)
            i = n if end < 0 else end
            continue
        if sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        out.append(ch)
        i += 1
    lines = [line.rstrip() for line in "".join(out).splitlines()]
    return "\n".join(line for line in lines if line.strip())


def split_statements(script: str) -> List[str]:
    """Split a script into complete statements (trigger bodies included), comments removed.

    `executescript` cannot be used inside a transaction: it commits first.
    """
    statements: List[str] = []
    buffer: List[str] = []
    for ch in script:
        buffer.append(ch)
        if ch == ";":
            text = "".join(buffer)
            if sqlite3.complete_statement(text):
                statement = strip_comments(text).strip()
                if statement and statement != ";":
                    statements.append(statement)
                buffer = []
    if strip_comments("".join(buffer)).strip():
        raise ValueError("SQL script ends with an unterminated statement")
    return statements


__all__ = ["split_statements", "strip_comments"]
