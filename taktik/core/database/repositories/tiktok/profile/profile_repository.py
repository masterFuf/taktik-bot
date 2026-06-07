"""TikTok profile repository methods."""

from typing import Any, Dict, Optional, Tuple

from loguru import logger


class TikTokProfileRepositoryMixin:
    """SQL owner for `tiktok_profiles` and scraped-profile links."""

    def get_or_create_profile(self, username: str, **kwargs) -> Tuple[int, bool]:
        """Get or create a TikTok profile"""
        row = self.query_one(
            "SELECT legacy_profile_id AS profile_id FROM social_profiles WHERE platform = 'tiktok' AND username = ?",
            (username,)
        )

        if row:
            profile_id = row['profile_id']
            self._update_profile(profile_id, **kwargs)
            return profile_id, False

        # Unified social_profiles (platform='tiktok'); videos_count maps to posts_count;
        # legacy_profile_id generated atomically.
        self.execute(
            """INSERT INTO social_profiles (
                platform, legacy_profile_id, username, display_name, followers_count, following_count,
                likes_count, posts_count, is_private, is_verified, biography
            ) SELECT 'tiktok',
                COALESCE((SELECT MAX(legacy_profile_id) FROM social_profiles WHERE platform='tiktok'), 0) + 1,
                ?, ?, ?, ?, ?, ?, ?, ?, ?""",
            (
                username,
                kwargs.get('display_name', ''),
                kwargs.get('followers_count', 0),
                kwargs.get('following_count', 0),
                kwargs.get('likes_count', 0),
                kwargs.get('videos_count', 0),
                1 if kwargs.get('is_private') else 0,
                1 if kwargs.get('is_verified') else 0,
                kwargs.get('biography')
            )
        )
        created = self.query_one(
            "SELECT legacy_profile_id AS profile_id FROM social_profiles WHERE platform = 'tiktok' AND username = ?",
            (username,)
        )
        return (created['profile_id'] if created else None), True

    def _update_profile(self, profile_id: int, **kwargs) -> None:
        """Update profile with non-None values (unified social_profiles, platform='tiktok')."""
        updates = []
        values = []
        # videos_count maps to social_profiles.posts_count
        colmap = {'videos_count': 'posts_count'}

        for key in ('display_name', 'biography'):
            if kwargs.get(key):
                updates.append(f"{key} = COALESCE(?, {key})")
                values.append(kwargs[key])

        for key in ('followers_count', 'following_count', 'likes_count', 'videos_count'):
            value = kwargs.get(key)
            if value and value > 0:
                col = colmap.get(key, key)
                updates.append(f"{col} = ?")
                values.append(value)

        for key in ('is_private', 'is_verified'):
            if key in kwargs and kwargs[key] is not None:
                updates.append(f"{key} = COALESCE(?, {key})")
                values.append(1 if kwargs[key] else 0)

        if updates:
            updates.append("updated_at = datetime('now')")
            values.append(profile_id)
            self.execute(
                f"UPDATE social_profiles SET {', '.join(updates)} WHERE platform = 'tiktok' AND legacy_profile_id = ?",
                tuple(values)
            )

    def find_profile_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Find profile by username"""
        row = self.query_one(
            "SELECT * FROM tiktok_profiles WHERE username = ?",
            (username,)
        )
        return self._map_profile_row(row)

    def link_scraped_profile(self, scraping_id: int, profile_id: int, is_enriched: bool = False) -> bool:
        """Link a scraped profile to a scraping session via junction table."""
        try:
            self.execute(
                """INSERT OR IGNORE INTO scraped_profiles (platform, scraping_id, profile_id, is_enriched)
                   VALUES ('tiktok', ?, ?, ?)""",
                (scraping_id, profile_id, 1 if is_enriched else 0)
            )
            return True
        except Exception as e:
            logger.error(f"Error linking scraped profile: {e}")
            return False

    def save_scraped_profile(self, scraping_id: int, profile: dict) -> None:
        """Upsert a TikTok profile and link it to a scraping session."""
        username = profile.get('username', '')
        if not username:
            return

        profile_id, _ = self.get_or_create_profile(
            username,
            display_name=profile.get('display_name', ''),
            followers_count=profile.get('followers_count', 0),
            following_count=profile.get('following_count', 0),
            likes_count=profile.get('likes_count', 0),
            videos_count=profile.get('posts_count', 0),
            is_private=profile.get('is_private', False),
            is_verified=profile.get('is_verified', False),
            biography=profile.get('bio', '')
        )

        if scraping_id:
            self.link_scraped_profile(scraping_id, profile_id, profile.get('is_enriched', False))

    def _map_profile_row(self, row) -> Optional[Dict[str, Any]]:
        """Map database row to dict"""
        if row is None:
            return None
        row_dict = dict(row)
        return {
            **row_dict,
            'is_private': bool(row_dict.get('is_private', 0)),
            'is_verified': bool(row_dict.get('is_verified', 0))
        }
