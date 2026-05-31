"""TikTok filtered-profile repository methods."""

from typing import Optional

from loguru import logger


class TikTokFilteredProfileRepositoryMixin:
    """SQL owner for `tiktok_filtered_profiles`."""

    def is_profile_filtered(self, username: str, account_id: int) -> bool:
        """Check if a profile is filtered"""
        row = self.query_one(
            "SELECT COUNT(*) as count FROM tiktok_filtered_profiles WHERE username = ? AND account_id = ?",
            (username, account_id)
        )
        return (row['count'] if row else 0) > 0

    def record_filtered_profile(
        self,
        account_id: int,
        profile_id: int,
        username: str,
        reason: str,
        source_type: str = 'GENERAL',
        source_name: str = 'unknown',
        session_id: Optional[int] = None
    ) -> bool:
        """Record a filtered profile"""
        try:
            self.execute(
                """INSERT OR REPLACE INTO tiktok_filtered_profiles
                   (profile_id, account_id, username, reason, source_type, source_name, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (profile_id, account_id, username, reason, source_type, source_name, session_id)
            )
            return True
        except Exception as e:
            logger.error(f"Error recording filtered TikTok profile: {e}")
            return False

    def record_filtered_profile_for_username(
        self,
        account_id: int,
        username: str,
        reason: str,
        source_type: str,
        source_name: str,
        session_id: Optional[int] = None,
    ) -> bool:
        """Record a filtered TikTok profile, creating the profile row if needed."""
        try:
            profile_id, _ = self.get_or_create_profile(username)
            result = self.record_filtered_profile(
                account_id=account_id,
                profile_id=profile_id,
                username=username,
                reason=reason,
                source_type=source_type,
                source_name=source_name,
                session_id=session_id,
            )
            if result:
                logger.debug(f"Recorded TikTok filtered profile: {username} ({reason})")
            return result
        except Exception as e:
            logger.error(f"Error recording TikTok filtered profile: {e}")
            return False
