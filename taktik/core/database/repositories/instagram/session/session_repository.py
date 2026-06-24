"""
Session Repository - Manages sessions and scraping_sessions tables
"""

import json
from typing import Dict, List, Optional, Any
from loguru import logger
from ..._base.base_repository import BaseRepository


class SessionRepository(BaseRepository):
    """Repository for automation and scraping sessions"""
    
    # ============================================
    # AUTOMATION SESSIONS
    # ============================================
    
    def create(
        self,
        account_id: int,
        session_name: str,
        target_type: str,
        target: str,
        config_used: Optional[dict] = None
    ) -> Optional[int]:
        """Create a new automation session (unified sessions_unified, platform='instagram')."""
        try:
            # session_id = per-platform legacy_session_id, generated atomically (single
            # INSERT ... SELECT MAX+1 runs under SQLite's write lock -> collision-free
            # across the bot + Electron processes).
            cursor = self.execute(
                """INSERT INTO sessions_unified
                       (platform, legacy_session_id, account_id, session_name, target_type, target,
                        config_used, status, start_time, created_at, updated_at, sync_id)
                   SELECT 'instagram',
                          COALESCE((SELECT MAX(legacy_session_id) FROM sessions_unified WHERE platform='instagram'), 0) + 1,
                          ?, ?, ?, ?, ?, 'ACTIVE', datetime('now'), datetime('now'), datetime('now'), lower(hex(randomblob(16)))""",
                (
                    account_id,
                    session_name[:100],
                    target_type,
                    target[:50],
                    json.dumps(self._redact_sensitive(config_used)) if config_used else None
                )
            )
            row = self.query_one(
                "SELECT legacy_session_id FROM sessions_unified WHERE id = ?",
                (cursor.lastrowid,)
            )
            return row['legacy_session_id'] if row else None
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None
    
    def update(
        self,
        session_id: int,
        status: Optional[str] = None,
        end_time: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Update session"""
        updates = ["updated_at = datetime('now')"]
        values = []
        
        if status:
            updates.append('status = ?')
            values.append(status)
        if end_time:
            updates.append('end_time = ?')
            values.append(end_time)
        if duration_seconds is not None:
            updates.append('duration_seconds = ?')
            values.append(duration_seconds)
        if error_message:
            updates.append('error_message = ?')
            values.append(error_message)
        
        values.append(session_id)
        cursor = self.execute(
            f"UPDATE sessions_unified SET {', '.join(updates)} WHERE platform = 'instagram' AND legacy_session_id = ?",
            tuple(values)
        )
        return cursor.rowcount > 0

    def find_by_id(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Find session by ID (ORM-first, fallback to raw sqlite3)."""
        row = self.query_one_orm_first(
            "SELECT *, legacy_session_id AS session_id FROM sessions_unified "
            "WHERE platform = 'instagram' AND legacy_session_id = ?",
            (session_id,)
        )
        return self._map_session_row(row)

    def find_by_account(self, account_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get sessions by account (ORM-first, fallback to raw sqlite3)."""
        rows = self.query_orm_first(
            "SELECT *, legacy_session_id AS session_id FROM sessions_unified "
            "WHERE platform = 'instagram' AND account_id = ? ORDER BY start_time DESC LIMIT ?",
            (account_id, limit)
        )
        return [self._map_session_row(row) for row in rows]

    def find_active(self) -> List[Dict[str, Any]]:
        """Get active sessions (ORM-first, fallback to raw sqlite3)."""
        rows = self.query_orm_first(
            "SELECT *, legacy_session_id AS session_id FROM sessions_unified "
            "WHERE platform = 'instagram' AND status = 'ACTIVE' ORDER BY start_time DESC"
        )
        return [self._map_session_row(row) for row in rows]

    def find_unsynced(self) -> List[Dict[str, Any]]:
        """Get unsynced sessions (ORM-first, fallback to raw sqlite3)."""
        rows = self.query_orm_first(
            "SELECT *, legacy_session_id AS session_id FROM sessions_unified "
            "WHERE platform = 'instagram' AND synced_to_api = 0 AND status IN ('COMPLETED', 'FAILED', 'ERROR') "
            "ORDER BY start_time DESC"
        )
        return [self._map_session_row(row) for row in rows]

    def mark_as_synced(self, session_ids: List[int]) -> bool:
        """Mark sessions as synced"""
        if not session_ids:
            return True

        placeholders = ','.join('?' * len(session_ids))
        cursor = self.execute(
            f"UPDATE sessions_unified SET synced_to_api = 1 "
            f"WHERE platform = 'instagram' AND legacy_session_id IN ({placeholders})",
            tuple(session_ids)
        )
        return cursor.rowcount > 0

    # ============================================
    # SCRAPING SESSIONS
    # ============================================
    
    def create_scraping(
        self,
        scraping_type: str,
        source_type: str,
        source_name: str,
        account_id: Optional[int] = None,
        max_profiles: int = 500,
        export_csv: bool = False,
        save_to_db: bool = True,
        config_used: Optional[dict] = None,
        platform: str = 'instagram'
    ) -> Optional[int]:
        """Create a new scraping session"""
        try:
            cursor = self.execute(
                # sync_id is generated here (like sessions_unified above) so the row carries a
                # stable cross-device key from creation. Without it the column stays NULL and the
                # Turso push, which upserts on sync_id (PRIMARY KEY), re-inserts the row every
                # cycle (SQLite treats NULL as distinct from NULL) -> runaway remote duplicates.
                """INSERT INTO scraping_sessions (
                    account_id, scraping_type, source_type, source_name,
                    max_profiles, export_csv, save_to_db, config_used, platform, sync_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, lower(hex(randomblob(16))))""",
                (
                    account_id,
                    scraping_type,
                    source_type,
                    source_name,
                    max_profiles,
                    1 if export_csv else 0,
                    1 if save_to_db else 0,
                    json.dumps(self._redact_sensitive(config_used)) if config_used else None,
                    platform
                )
            )
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error creating scraping session: {e}")
            return None
    
    def update_scraping(
        self,
        scraping_id: int,
        total_scraped: Optional[int] = None,
        status: Optional[str] = None,
        end_time: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        error_message: Optional[str] = None,
        csv_path: Optional[str] = None
    ) -> bool:
        """Update scraping session"""
        updates = []
        values = []
        
        if total_scraped is not None:
            updates.append('total_scraped = ?')
            values.append(total_scraped)
        if status:
            updates.append('status = ?')
            values.append(status)
        if end_time:
            updates.append('end_time = ?')
            values.append(end_time)
        if duration_seconds is not None:
            updates.append('duration_seconds = ?')
            values.append(duration_seconds)
        if error_message:
            updates.append('error_message = ?')
            values.append(error_message)
        if csv_path:
            updates.append('csv_path = ?')
            values.append(csv_path)
        
        if not updates:
            return False
        
        values.append(scraping_id)
        cursor = self.execute(
            f"UPDATE scraping_sessions SET {', '.join(updates)} WHERE scraping_id = ?",
            tuple(values)
        )
        return cursor.rowcount > 0
    
    def find_scraping_by_id(self, scraping_id: int) -> Optional[Dict[str, Any]]:
        """Find scraping session by ID (ORM-first, fallback to raw sqlite3)."""
        row = self.query_one_orm_first(
            "SELECT * FROM scraping_sessions WHERE scraping_id = ?",
            (scraping_id,)
        )
        return self._map_scraping_row(row)

    def find_all_scraping(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all scraping sessions (ORM-first, fallback to raw sqlite3)."""
        rows = self.query_orm_first(
            "SELECT * FROM scraping_sessions ORDER BY start_time DESC LIMIT ?",
            (limit,)
        )
        return [self._map_scraping_row(row) for row in rows]

    def find_scraping_by_type(self, scraping_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get scraping sessions by type (ORM-first, fallback to raw sqlite3)."""
        rows = self.query_orm_first(
            "SELECT * FROM scraping_sessions WHERE scraping_type = ? ORDER BY start_time DESC LIMIT ?",
            (scraping_type, limit)
        )
        return [self._map_scraping_row(row) for row in rows]
    
    def cleanup_orphan_scraping(self) -> int:
        """Cleanup orphan scraping sessions (stuck in RUNNING status)"""
        cursor = self.execute(
            """UPDATE scraping_sessions 
               SET status = 'INTERRUPTED', end_time = datetime('now')
               WHERE status = 'RUNNING' 
               AND start_time < datetime('now', '-2 hours')"""
        )
        return cursor.rowcount
    
    def _map_session_row(self, row) -> Optional[Dict[str, Any]]:
        """Map database row to dict"""
        if row is None:
            return None
        row_dict = dict(row)
        return {
            **row_dict,
            'synced_to_api': bool(row_dict.get('synced_to_api', 0))
        }
    
    def _map_scraping_row(self, row) -> Optional[Dict[str, Any]]:
        """Map database row to dict"""
        if row is None:
            return None
        row_dict = dict(row)
        return {
            **row_dict,
            'export_csv': bool(row_dict.get('export_csv', 0)),
            'save_to_db': bool(row_dict.get('save_to_db', 1))
        }
