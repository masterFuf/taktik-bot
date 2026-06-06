"""TikTok session lifecycle repository methods."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from ....local.migration_steps.sessions import TT_SESSION_COLS, build_session_copy_sql


class TikTokSessionRepositoryMixin:
    """SQL owner for the `tiktok_sessions` lifecycle."""

    def create_session(
        self,
        account_id: int,
        session_name: str,
        workflow_type: str,
        target: Optional[str] = None,
        config_used: Optional[dict] = None
    ) -> Optional[int]:
        """Create a new TikTok session"""
        try:
            cursor = self.execute(
                """INSERT INTO tiktok_sessions (account_id, session_name, workflow_type, target, config_used)
                   VALUES (?, ?, ?, ?, ?)""",
                (account_id, session_name[:100], workflow_type, target[:50] if target else None,
                 json.dumps(self._redact_sensitive(config_used)) if config_used else None)
            )
            session_id = cursor.lastrowid
            self._mirror_session(session_id)
            return session_id
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
            f"UPDATE tiktok_sessions SET {', '.join(updates)} WHERE session_id = ?",
            tuple(values)
        )
        self._mirror_session(session_id)
        return cursor.rowcount > 0

    def _mirror_session(self, session_id: int) -> None:
        """Mirror one TikTok session row into sessions_unified (Vague B Phase A).
        Best-effort, column-aware; idempotent via UNIQUE(platform, legacy_session_id)."""
        try:
            sql = build_session_copy_sql(
                self.conn.cursor(), "tiktok", "tiktok_sessions", TT_SESSION_COLS,
                verb="INSERT OR REPLACE", where="WHERE session_id = ?",
            )
            self.execute(sql, (session_id,))
        except Exception as exc:
            logger.debug(f"sessions_unified mirror (tiktok) failed: {exc}")

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
                "SELECT start_time FROM tiktok_sessions WHERE session_id = ?",
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
        query = "SELECT * FROM tiktok_sessions WHERE 1=1"
        params = []

        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)

        if workflow_type:
            query += " AND workflow_type = ?"
            params.append(workflow_type)

        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)

        return [dict(row) for row in self.query(query, tuple(params))]

    def get_sessions_by_account(self, account_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get sessions by account"""
        rows = self.query(
            "SELECT * FROM tiktok_sessions WHERE account_id = ? ORDER BY start_time DESC LIMIT ?",
            (account_id, limit)
        )
        return [dict(row) for row in rows]

    def get_all_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all sessions"""
        rows = self.query(
            "SELECT * FROM tiktok_sessions ORDER BY start_time DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in rows]

    def get_session_stats(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Get session stats"""
        row = self.query_one(
            "SELECT * FROM tiktok_sessions WHERE session_id = ?",
            (session_id,)
        )
        return dict(row) if row else None
