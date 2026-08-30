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
        post_key: Optional[str] = None,
    ) -> Optional[int]:
        """Store (or refresh) one post.

        Upsert on (platform, **post_key**), not on the URL. On Instagram the two are the same
        thing — a share link carries a per-copy `?igsh=` token, normalisation strips it, and what
        is left is a stable canonical form — so `post_key` defaults to the normalised URL and
        nothing changes for that platform.

        TikTok has no canonical link. Measured 2026-08-30: "Copy link" mints a whole new short
        link on every copy, four copies of one video giving four URLs, and no numeric video id is
        rendered anywhere. Keyed on the URL, one video would be stored once per visit and
        `find_by_url` would never hit the row it already held. Callers on that platform pass a key
        built from what the screen shows stably (see `tiktok_post_key`).

        `post_url` is REFRESHED on conflict: on TikTok the newest copy is the one most likely to
        still resolve, and on Instagram it re-normalises to the same string anyway.

        A None counter never erases a known one (a read can fail on a post we already measured);
        `first_seen_at` is kept across refreshes.
        """
        # Normalisation is Instagram's, not the table's: `canonical_post_url` demands an
        # Instagram shortcode and returns None for anything else. Running a TikTok link through
        # it threw the post away with "unusable url" — the URL was perfectly usable, it simply
        # was not an Instagram one.
        url = canonical_post_url(post_url) if platform == "instagram" else (post_url or "").strip()
        author = (author_username or "").strip().lstrip("@").lower()
        key = (post_key or "").strip() or url
        if not url or not author:
            logger.warning(f"Post not recorded: unusable url/author ({post_url!r}, {author_username!r})")
            return None
        try:
            cursor = self.execute(
                """INSERT INTO social_posts
                   (platform, sync_id, post_key, post_url, author_username, likes_count,
                    comments_count, first_seen_at, last_scraped_at)
                   VALUES (?, lower(hex(randomblob(16))), ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))
                   ON CONFLICT(platform, post_key) DO UPDATE SET
                     post_url = excluded.post_url,
                     likes_count = COALESCE(excluded.likes_count, likes_count),
                     comments_count = COALESCE(excluded.comments_count, comments_count),
                     last_scraped_at = excluded.last_scraped_at""",
                (platform, key, url, author, likes_count, comments_count),
            )
            return cursor.lastrowid
        except Exception as exc:
            logger.error(f"Error recording post {url}: {exc}")
            return None

    def find_by_key(self, post_key: str, platform: str = 'instagram') -> Optional[Dict[str, Any]]:
        """The stored post behind this identity, whatever URL it was last seen at."""
        key = (post_key or "").strip()
        if not key:
            return None
        try:
            return self.query_one_orm_first(
                "SELECT * FROM social_posts WHERE platform = ? AND post_key = ?",
                (platform, key),
            )
        except Exception as exc:
            logger.error(f"Error reading post {key}: {exc}")
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
