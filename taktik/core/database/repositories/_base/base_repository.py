"""
Base Repository - Abstract class for all repositories
Provides common database operations and connection management
"""

import sqlite3
from typing import Any, Dict, List, Optional, Tuple, TypeVar, Generic
from abc import ABC

from loguru import logger

T = TypeVar('T')


class BaseRepository(ABC):
    """Base class for all repositories"""

    def __init__(self, connection: sqlite3.Connection, orm_engine: Any = None):
        self._conn = connection
        self._conn.row_factory = sqlite3.Row
        # ORM cutover (Vague D): optional SQLAlchemy engine. When present, the read
        # helpers route through it (ORM-first) and fall back to raw sqlite3 on any error.
        # None on standalone-bridge bases (factory) -> reads stay on raw sqlite3.
        # SQLAlchemy is synchronous, so the ORM-first decision lives inside the read
        # method: callers are unaffected (no async ripple, unlike the front).
        self._orm_engine = orm_engine

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def query(self, sql: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Execute a query and return all results"""
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()

    def query_one(self, sql: str, params: Tuple = ()) -> Optional[sqlite3.Row]:
        """Execute a query and return the first result"""
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchone()

    def _orm_rows(self, sql: str, params: Tuple) -> List[Dict[str, Any]]:
        """Run the SAME ``?``-parameterised SQL through the SQLAlchemy engine's pooled
        DBAPI connection and return dict rows (column names from the cursor description,
        so an aliased ``SELECT *, x AS y`` reproduces the raw shape exactly)."""
        raw = self._orm_engine.raw_connection()
        try:
            cursor = raw.cursor()
            cursor.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
        finally:
            raw.close()

    def query_orm_first(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """ORM-first read (SQLAlchemy engine) with a full fallback to raw sqlite3.
        Returns list[dict]. Same SQL on both paths -> identical results by construction."""
        if self._orm_engine is not None:
            try:
                return self._orm_rows(sql, params)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug(f"ORM read failed, falling back to sqlite3: {exc}")
        return [dict(row) for row in self.query(sql, params)]

    def query_one_orm_first(self, sql: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        """Single-row ORM-first read with a full fallback to raw sqlite3."""
        if self._orm_engine is not None:
            try:
                rows = self._orm_rows(sql, params)
                return rows[0] if rows else None
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug(f"ORM read failed, falling back to sqlite3: {exc}")
        row = self.query_one(sql, params)
        return dict(row) if row is not None else None
    
    def execute(self, sql: str, params: Tuple = ()) -> sqlite3.Cursor:
        """Execute an insert/update/delete and return the cursor"""
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        self._conn.commit()
        return cursor
    
    def execute_many(self, sql: str, params_list: List[Tuple]) -> int:
        """Execute multiple statements and return affected rows"""
        cursor = self._conn.cursor()
        cursor.executemany(sql, params_list)
        self._conn.commit()
        return cursor.rowcount
    
    def column_exists(self, table: str, column: str) -> bool:
        """Check if a column exists in a table"""
        cursor = self._conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        return column in columns
    
    def add_column_if_not_exists(self, table: str, column: str, definition: str) -> bool:
        """Add a column if it doesn't exist"""
        if not self.column_exists(table, column):
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            self._conn.commit()
            return True
        return False
    
    def row_to_dict(self, row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        """Convert a sqlite3.Row to a dictionary"""
        if row is None:
            return None
        return dict(row)
    
    def rows_to_dicts(self, rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
        """Convert a list of sqlite3.Row to a list of dictionaries"""
        return [dict(row) for row in rows]

    # ----------------------------------------------------------------
    # Security helpers
    # ----------------------------------------------------------------

    # Keys that must never be stored in plaintext in the database
    _SENSITIVE_KEYS = frozenset({
        'openrouterApiKey', 'openrouter_api_key', 'apiKey', 'api_key',
        'password', 'token', 'secret', 'accessToken', 'access_token',
        'refreshToken', 'refresh_token', 'privateKey', 'private_key',
    })

    @classmethod
    def _redact_sensitive(cls, config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Return a copy of *config* with all sensitive keys replaced by '***REDACTED***'.

        Call this before serialising a config dict to JSON for DB storage so that
        API keys and passwords are never persisted in plaintext.
        """
        if not config:
            return config
        redacted = {}
        for k, v in config.items():
            if k in cls._SENSITIVE_KEYS:
                redacted[k] = '***REDACTED***'
            elif isinstance(v, dict):
                redacted[k] = cls._redact_sensitive(v)
            else:
                redacted[k] = v
        return redacted
