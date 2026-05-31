"""Repository adapter for the TikTok Followers workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TikTokFollowersSessionRef:
    account_id: Optional[int]
    session_id: Optional[int]


class TikTokFollowersRepository:
    """Encapsulate SQLite operations used by the TikTok Followers workflow."""

    def __init__(self, db: Any = None):
        if db is None:
            from taktik.core.database.local.service import get_local_database

            db = get_local_database()
        self._db = db

    def create_session(
        self,
        *,
        bot_username: Optional[str],
        target: str,
        config_used: Optional[Dict[str, Any]],
    ) -> TikTokFollowersSessionRef:
        if not bot_username:
            return TikTokFollowersSessionRef(account_id=None, session_id=None)

        account_id, _ = self._db.get_or_create_tiktok_account(bot_username)
        session_id = self._db.create_tiktok_session(
            account_id=account_id,
            session_name=f"Followers @{target}",
            workflow_type="FOLLOWERS",
            target=target,
            config_used=config_used,
        )
        return TikTokFollowersSessionRef(account_id=account_id, session_id=session_id)

    def end_session(
        self,
        *,
        account_id: Optional[int],
        session_id: Optional[int],
        status: str,
        error_message: Optional[str],
        stats: Dict[str, Any],
    ) -> None:
        if not session_id or not account_id:
            return

        self._db.end_tiktok_session(
            session_id=session_id,
            status=status,
            error_message=error_message,
            stats=stats,
        )

    def has_recent_interaction(
        self,
        *,
        account_id: Optional[int],
        username: str,
        hours: int = 168,
    ) -> bool:
        if not account_id or not username:
            return False
        return bool(self._db.check_tiktok_recent_interaction(username, account_id, hours=hours))

    def has_interaction(self, *, account_id: Optional[int], username: str) -> bool:
        if not account_id or not username:
            return False
        return bool(self._db.has_tiktok_interaction(account_id, username))

    def count_recent_target_interactions(
        self,
        *,
        account_id: Optional[int],
        target: str,
        hours: int = 168,
    ) -> int:
        if not account_id or not target:
            return 0
        return int(self._db.count_tiktok_interactions_for_target(account_id, target, hours=hours))

    def save_profile(self, *, account_id: Optional[int], profile_data: Dict[str, Any]) -> bool:
        if not account_id:
            return False
        self._db.get_or_create_tiktok_profile(profile_data)
        return True

    def record_interaction(
        self,
        *,
        account_id: Optional[int],
        target_username: str,
        interaction_type: str,
        session_id: Optional[int],
        success: bool = True,
    ) -> None:
        if not account_id or not target_username:
            return
        self._db.record_tiktok_interaction(
            account_id=account_id,
            target_username=target_username,
            interaction_type=interaction_type,
            success=success,
            session_id=session_id,
        )
