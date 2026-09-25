"""Logical fingerprint of a SQLite schema, and the bot's part of it.

Bases that reached the same schema by different roads (created by the app first, by the bot
first, or upgraded over months) store different CREATE texts, column orders, defaults and
index names. The fingerprint keeps what reads and writes depend on: tables and their columns
(declared type, primary key), views and their columns, triggers, and unique keys.

A schema definition is the bot's part only: its tables, views, triggers and the unique keys on
its tables, plus the retired tables that must no longer exist. Objects of the desktop app are
never compared: the bot recognises a base by what it owns.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Dict, Iterable, List

_VIRTUAL_MODULE = re.compile(r"USING\s+(\w+)", re.I)


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _user_objects(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY type, name"
    ).fetchall()


def _unique_keys(conn: sqlite3.Connection, table: str) -> List[str]:
    keys = []
    pk = [row[1] for row in conn.execute(f"PRAGMA table_info({quote_identifier(table)})") if row[5]]
    if pk:
        keys.append(f"{table}({','.join(sorted(pk))})")
    for row in conn.execute(f"PRAGMA index_list({quote_identifier(table)})"):
        name, unique, partial = row[1], row[2], row[4]
        if not unique or partial:
            continue
        cols = [
            info[2] if info[2] is not None else "<expr>"
            for info in conn.execute(f"PRAGMA index_info({quote_identifier(name)})")
        ]
        keys.append(f"{table}({','.join(sorted(cols))})")
    return keys


def fingerprint(conn: sqlite3.Connection) -> Dict:
    """Fingerprint of every object seen by `conn` (uncommitted changes included)."""
    tables: Dict[str, Dict] = {}
    views: Dict[str, object] = {}
    triggers: Dict[str, str] = {}
    uniques = set()
    for typ, name, tbl_name, sql in _user_objects(conn):
        if typ == "table":
            columns = {
                row[1]: [(row[2] or "").upper(), row[5]]
                for row in conn.execute(f"PRAGMA table_xinfo({quote_identifier(name)})")
            }
            entry: Dict[str, object] = {"columns": dict(sorted(columns.items()))}
            if sql and sql.lstrip().upper().startswith("CREATE VIRTUAL TABLE"):
                match = _VIRTUAL_MODULE.search(sql)
                entry["module"] = match.group(1).lower() if match else "?"
            tables[name] = entry
            uniques.update(_unique_keys(conn, name))
        elif typ == "view":
            try:
                views[name] = sorted(
                    row[1] for row in conn.execute(f"PRAGMA table_xinfo({quote_identifier(name)})")
                )
            except sqlite3.Error as exc:
                views[name] = f"broken: {exc}"
        elif typ == "trigger":
            triggers[name] = tbl_name
    return {
        "tables": dict(sorted(tables.items())),
        "views": dict(sorted(views.items())),
        "triggers": dict(sorted(triggers.items())),
        "unique_keys": sorted(uniques),
    }


def scope(fp: Dict, tables: Iterable[str], views: Iterable[str] = (), triggers: Iterable[str] = (),
          retired_tables: Iterable[str] = ()) -> Dict:
    """The part of a fingerprint that belongs to one owner: a schema definition."""
    tables, views, triggers = set(tables), set(views), set(triggers)
    return {
        "tables": {k: v for k, v in fp["tables"].items() if k in tables},
        "views": {k: v for k, v in fp["views"].items() if k in views},
        "triggers": {k: v for k, v in fp["triggers"].items() if k in triggers},
        "unique_keys": [k for k in fp["unique_keys"] if k.split("(", 1)[0] in tables],
        "retired_tables": sorted(set(retired_tables)),
    }


def digest(fp: Dict) -> str:
    canonical = json.dumps(fp, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compare(expected: Dict, actual: Dict) -> List[str]:
    """Differences that make `actual` NOT carry the `expected` definition. Empty = it does.

    Only the objects of the definition are looked at. Anything else in the base (the desktop
    app's tables, views and triggers, any index that is not unique, an extra unique key) is
    not the bot's business and is ignored.
    """
    diffs: List[str] = []
    for name, spec in expected["tables"].items():
        act = actual["tables"].get(name)
        if act is None:
            where = "a view" if name in actual["views"] else "absent"
            diffs.append(f"missing table {name} ({where})")
            continue
        exp_cols, act_cols = spec["columns"], act["columns"]
        missing = sorted(set(exp_cols) - set(act_cols))
        extra = sorted(set(act_cols) - set(exp_cols))
        if missing:
            diffs.append(f"table {name}: missing columns {missing}")
        if extra:
            diffs.append(f"table {name}: unexpected columns {extra}")
        for col in sorted(set(exp_cols) & set(act_cols)):
            if exp_cols[col] != act_cols[col]:
                diffs.append(f"table {name}: column {col} is {act_cols[col]}, expected {exp_cols[col]}")
        if spec.get("module") != act.get("module"):
            diffs.append(f"table {name}: virtual module differs")

    for name, cols in expected["views"].items():
        if name not in actual["views"]:
            where = "a table" if name in actual["tables"] else "absent"
            diffs.append(f"missing view {name} ({where})")
        elif actual["views"][name] != cols:
            diffs.append(f"view {name}: columns differ")

    for name, table in expected.get("triggers", {}).items():
        if name not in actual["triggers"]:
            diffs.append(f"missing trigger {name}")
        elif actual["triggers"][name] != table:
            diffs.append(f"trigger {name}: on {actual['triggers'][name]}, expected {table}")

    act_keys = set(actual["unique_keys"])
    for key in expected["unique_keys"]:
        if key not in act_keys:
            diffs.append(f"missing unique key {key}")

    for name in expected.get("retired_tables", []):
        if name in actual["tables"]:
            diffs.append(f"retired table {name} still present")
    return diffs


__all__ = ["compare", "digest", "fingerprint", "quote_identifier", "scope"]
