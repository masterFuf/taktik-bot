"""TikTok session lifecycle repository methods."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger


class TikTokSessionRepositoryMixin:
    """SQL owner for the TikTok session lifecycle (unified sessions_unified)."""

    def create_session(
        self,
        account_id: int,
        session_name: str,
        workflow_type: str,
        target: Optional[str] = None,
        config_used: Optional[dict] = None
    ) -> Optional[int]:
        """Create a new TikTok session (unified sessions_unified, platform='tiktok')."""
        try:
            # session_id = per-platform legacy_session_id, generated atomically.
            cursor = self.execute(
                """INSERT INTO sessions_unified
                       (platform, legacy_session_id, account_id, session_name, workflow_type, target,
                        config_used, status, start_time, created_at, updated_at, sync_id)
                   SELECT 'tiktok',
                          COALESCE((SELECT MAX(legacy_session_id) FROM sessions_unified WHERE platform='tiktok'), 0) + 1,
                          ?, ?, ?, ?, ?, 'ACTIVE', datetime('now'), datetime('now'), datetime('now'), lower(hex(randomblob(16)))""",
                (account_id, session_name[:100], workflow_type, target[:50] if target else None,
                 json.dumps(self._redact_sensitive(config_used)) if config_used else None)
            )
            row = self.query_one(
                "SELECT legacy_session_id FROM sessions_unified WHERE id = ?",
                (cursor.lastrowid,)
            )
            return row['legacy_session_id'] if row else None
        except Exception as e:
            logger.error(f"Error creating TikTok session: {e}")
            return None

    def update_session(self, session_id: int, **kwargs) -> bool:
        """Update session stats"""
        updates = ["updated_at = datetime('now')"]
        values = []

        field_mapping = {
            'status': 'status',
            'end_time': 'end_time',
            'duration_seconds': 'duration_seconds',
            'profiles_visited': 'profiles_visited',
            'posts_watched': 'posts_watched',
            'likes': 'likes',
            'follows': 'follows',
            'favorites': 'favorites',
            'comments': 'comments',
            'shares': 'shares',
            'errors': 'errors',
            'error_message': 'error_message'
        }

        for key, column in field_mapping.items():
            if key in kwargs and kwargs[key] is not None:
                updates.append(f'{column} = ?')
                values.append(kwargs[key])

        if len(updates) == 1:  # Only updated_at
            return True

        values.append(session_id)
        cursor = self.execute(
            f"UPDATE sessions_unified SET {', '.join(updates)} WHERE platform = 'tiktok' AND legacy_session_id = ?",
            tuple(values)
        )
        return cursor.rowcount > 0

    def end_session(
        self,
        session_id: int,
        status: str = 'COMPLETED',
        error_message: Optional[str] = None,
        stats: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """End a TikTok session with final stats."""
        try:
            row = self.query_one(
                "SELECT start_time FROM sessions_unified WHERE platform = 'tiktok' AND legacy_session_id = ?",
                (session_id,),
            )

            duration = 0
            if row and row['start_time']:
                start = datetime.fromisoformat(row['start_time'].replace('Z', '+00:00'))
                duration = int((datetime.now() - start.replace(tzinfo=None)).total_seconds())

            update_data = {
                'status': status,
                'end_time': datetime.now().isoformat(),
                'duration_seconds': duration,
                'error_message': error_message,
            }

            if stats:
                update_data.update({
                    'profiles_visited': stats.get('profiles_visited', 0),
                    'posts_watched': stats.get('posts_watched', 0),
                    'likes': stats.get('likes', 0),
                    'follows': stats.get('follows', 0),
                    'favorites': stats.get('favorites', 0),
                    'comments': stats.get('comments', 0),
                    'shares': stats.get('shares', 0),
                    'errors': stats.get('errors', 0),
                })

            return self.update_session(session_id, **update_data)
        except Exception as e:
            logger.error(f"Error ending TikTok session: {e}")
            return False

    def get_sessions(
        self,
        account_id: Optional[int] = None,
        limit: int = 50,
        workflow_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get TikTok sessions with optional filters."""
        query = "SELECT *, legacy_session_id AS session_id FROM sessions_unified WHERE platform = 'tiktok'"
        params = []

        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)

        if workflow_type:
            query += " AND workflow_type = ?"
            params.append(workflow_type)

        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)

        return [dict(row) for row in self.query_orm_first(query, tuple(params))]

    def get_sessions_by_account(self, account_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get sessions by account (ORM-first, fallback raw)."""
        rows = self.query_orm_first(
            "SELECT *, legacy_session_id AS session_id FROM sessions_unified "
            "WHERE platform = 'tiktok' AND account_id = ? ORDER BY start_time DESC LIMIT ?",
            (account_id, limit)
        )
        return [dict(row) for row in rows]

    def get_all_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all sessions (ORM-first, fallback raw)."""
        rows = self.query_orm_first(
            "SELECT *, legacy_session_id AS session_id FROM sessions_unified "
            "WHERE platform = 'tiktok' ORDER BY start_time DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in rows]

    def get_session_stats(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Get session stats (ORM-first, fallback raw)."""
        row = self.query_one_orm_first(
            "SELECT *, legacy_session_id AS session_id FROM sessions_unified "
            "WHERE platform = 'tiktok' AND legacy_session_id = ?",
            (session_id,)
        )
        return dict(row) if row else None
