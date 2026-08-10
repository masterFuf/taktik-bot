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
    
    @staticmethod
    def _workflow_type_from_config(config_used: Optional[dict]) -> Optional[str]:
        """The workflow a run belongs to, read out of the config it was launched with.

        Every Instagram workflow already puts its name in `session_settings.workflow_type` — the
        value was simply never lifted into the column beside it. Deriving it here rather than
        adding a parameter keeps the two from ever disagreeing, and spares every call site a
        signature change to pass something it is already passing.
        """
        if not isinstance(config_used, dict):
            return None
        settings = config_used.get('session_settings')
        if not isinstance(settings, dict):
            return None
        value = settings.get('workflow_type')
        return str(value)[:50] if value else None

    def create(
        self,
        account_id: int,
        session_name: str,
        target_type: str,
        target: str,
        config_used: Optional[dict] = None,
        workflow_type: Optional[str] = None
    ) -> Optional[int]:
        """Create a new automation session (unified sessions_unified, platform='instagram').

        `workflow_type` defaults to whatever the config declares. Left unset on the column, a
        session records WHAT it targeted but never WHICH workflow produced it — which is what made
        the Sessions page, Analytics and the workflow chooser guess. TikTok has always stored it;
        Instagram never did, on 773 of 793 rows.
        """
        try:
            # session_id = per-platform legacy_session_id, generated atomically (single
            # INSERT ... SELECT MAX+1 runs under SQLite's write lock -> collision-free
            # across the bot + Electron processes).
            cursor = self.execute(
                """INSERT INTO sessions_unified
                       (platform, legacy_session_id, account_id, session_name, target_type, target,
                        workflow_type, config_used, status, start_time, created_at, updated_at, sync_id)
                   SELECT 'instagram',
                          COALESCE((SELECT MAX(legacy_session_id) FROM sessions_unified WHERE platform='instagram'), 0) + 1,
                          ?, ?, ?, ?, ?, ?, 'ACTIVE', datetime('now'), datetime('now'), datetime('now'), lower(hex(randomblob(16)))""",
                (
                    account_id,
                    session_name[:100],
                    target_type,
                    target[:50],
                    workflow_type or self._workflow_type_from_config(config_used),
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

    def finalize(
        self,
        session_id: int,
        status: str,
        duration_seconds: Optional[int] = None,
        error_message: Optional[str] = None,
        posts_engaged: Optional[int] = None
    ) -> bool:
        """Terminal update: status + end_time + the stats_* snapshot aggregated from
        `interactions`.

        The snapshot mirrors Electron's resolveSessionStats semantics exactly:
        stats_total_interactions = likes + follows + comments + story_views + story_likes
        (unfollows and profile visits are tracked but excluded from the total). Electron
        only writes this snapshot on its own manual-stop path, so a session the bot ends
        itself (COMPLETED / INTERRUPTED / ERROR) must write it here — the plain update()
        used to persist only status+duration, leaving stats_* at 0 and end_time NULL even
        though the interactions rows prove the work happened.
        """
        agg_rows = self.query(
            """SELECT interaction_type, COUNT(*) AS count FROM interactions
               WHERE platform = 'instagram' AND session_id = ?
               GROUP BY interaction_type""",
            (session_id,)
        )
        agg = {str(row['interaction_type']).lower(): int(row['count']) for row in agg_rows}
        likes = agg.get('like', 0)
        follows = agg.get('follow', 0)
        unfollows = agg.get('unfollow', 0)
        comments = agg.get('comment', 0)
        story_views = agg.get('story_watch', 0)
        story_likes = agg.get('story_like', 0)
        profile_visits = agg.get('profile_visit', 0)
        total = likes + follows + comments + story_views + story_likes

        updates = [
            "updated_at = datetime('now')",
            "end_time = datetime('now')",
            'status = ?',
            'stats_total_interactions = ?',
            'stats_likes = ?',
            'stats_follows = ?',
            'stats_unfollows = ?',
            'stats_comments = ?',
            'stats_story_views = ?',
            'stats_story_likes = ?',
            'stats_profile_visits = ?',
        ]
        values: List[Any] = [status, total, likes, follows, unfollows, comments,
                             story_views, story_likes, profile_visits]

        # Engaged POSTS. The rest of the snapshot aggregates from the interactions table,
        # which is PER PROFILE: a run that opens no profile would otherwise report an
        # seuls ») n'y ecrit rien et ressortait donc entierement a zero — puis masque comme
        # empty session. This counter comes from the run itself, not from an aggregation.
        if posts_engaged is not None:
            updates.append('posts_watched = ?')
            values.append(int(posts_engaged))


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
