"""
Social-post repository — the posts collected on target accounts.

Owner of the `social_posts` table (see local/schemas/social_posts.py). Bot is the sole
writer; the desktop reads it to see what the collector found.
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from ..._base.base_repository import BaseRepository
from ....instagram_post_identity import canonical_post_url


class SocialPostRepository(BaseRepository):
    """Repository for the collected posts."""

    def record(
        self,
        post_url: str,
        author_username: str,
        likes_count: Optional[int] = None,
        comments_count: Optional[int] = None,
        platform: str = 'instagram',
    ) -> Optional[int]:
        """Store (or refresh) one post.

        Upsert on (platform, post_url) after normalising the URL, so every copy of a share
        link lands on the same row. A None counter never erases a known one (a read can fail
        on a post we already measured); `first_seen_at` is kept across refreshes.
        """
        url = canonical_post_url(post_url)
        author = (author_username or "").strip().lstrip("@").lower()
        if not url or not author:
            logger.warning(f"Post not recorded: unusable url/author ({post_url!r}, {author_username!r})")
            return None
        try:
            cursor = self.execute(
                """INSERT INTO social_posts
                   (platform, sync_id, post_url, author_username, likes_count, comments_count,
                    first_seen_at, last_scraped_at)
                   VALUES (?, lower(hex(randomblob(16))), ?, ?, ?, ?,
                           datetime('now'), datetime('now'))
                   ON CONFLICT(platform, post_url) DO UPDATE SET
                     likes_count = COALESCE(excluded.likes_count, likes_count),
                     comments_count = COALESCE(excluded.comments_count, comments_count),
                     last_scraped_at = excluded.last_scraped_at""",
                (platform, url, author, likes_count, comments_count),
            )
            return cursor.lastrowid
        except Exception as exc:
            logger.error(f"Error recording post {url}: {exc}")
            return None

    def find_by_url(self, post_url: str, platform: str = 'instagram') -> Optional[Dict[str, Any]]:
        """The stored post behind this URL (any copy of it), or None."""
        url = canonical_post_url(post_url)
        if not url:
            return None
        try:
            return self.query_one_orm_first(
                "SELECT * FROM social_posts WHERE platform = ? AND post_url = ?",
                (platform, url),
            )
        except Exception as exc:
            logger.error(f"Error reading post {url}: {exc}")
            return None

    def list_for_author(
        self, author_username: str, platform: str = 'instagram', limit: int = 100
    ) -> List[Dict[str, Any]]:
        """This account's collected posts, most liked first."""
        author = (author_username or "").strip().lstrip("@").lower()
        if not author:
            return []
        try:
            return self.query_orm_first(
                """SELECT * FROM social_posts
                   WHERE platform = ? AND author_username = ?
                   ORDER BY likes_count DESC, last_scraped_at DESC
                   LIMIT ?""",
                (platform, author, int(limit)),
            )
        except Exception as exc:
            logger.error(f"Error listing posts for {author}: {exc}")
            return []

    def count_for_author(self, author_username: str, platform: str = 'instagram') -> int:
        """How many of this account's posts are stored."""
        author = (author_username or "").strip().lstrip("@").lower()
        if not author:
            return 0
        try:
            row = self.query_one_orm_first(
                "SELECT COUNT(*) AS n FROM social_posts WHERE platform = ? AND author_username = ?",
                (platform, author),
            )
            return int(row["n"]) if row else 0
        except Exception as exc:
            logger.error(f"Error counting posts for {author}: {exc}")
            return 0
