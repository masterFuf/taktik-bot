"""
Base Repository - Abstract class for all repositories
Provides common database operations and connection management
"""

import sqlite3
from typing import Any, Dict, List, Optional, Tuple, TypeVar, Generic
from abc import ABC

T = TypeVar('T')


class BaseRepository(ABC):
    """Base class for all repositories"""
    
    def __init__(self, connection: sqlite3.Connection):
        self._conn = connection
        self._conn.row_factory = sqlite3.Row
    
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
