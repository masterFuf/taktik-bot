"""
Social-post repository — the catalogue of posts observed on target accounts.

Owner of the `social_posts` table (see local/schemas/social_posts.py for what is stored
and why the URL is the key). Bot is the sole writer; the desktop reads it to pick the
posts worth a `post_url` run.
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from ..._base.base_repository import BaseRepository
from ....instagram_post_identity import (
    canonical_post_url,
    post_shortcode_from_url,
    post_type_from_url,
)

# A preview is what the catalogue shows in a list; the full caption is not a fact worth a row.
CAPTION_PREVIEW_MAX = 300

# The only columns a caller may sort the catalogue by. Interpolated into SQL, hence closed.
_ORDERABLE_COLUMNS = ("likes_count", "comments_count", "last_scraped_at", "first_seen_at")


class SocialPostRepository(BaseRepository):
    """Repository for the post catalogue."""

    def find_by_url(self, post_url: str, platform: str = 'instagram') -> Optional[Dict[str, Any]]:
        """The catalogued post behind this URL (any copy of it), or None."""
        url = canonical_post_url(post_url)
        if not url:
            return None
        try:
            return self.query_one_orm_first(
                "SELECT * FROM social_posts WHERE platform = ? AND post_url = ?",
                (platform, url),
            )
        except Exception as exc:
            logger.error(f"Error reading social post {url}: {exc}")
            return None

    def find_by_ref(self, post_ref: str, platform: str = 'instagram') -> Optional[Dict[str, Any]]:
        """The catalogued post with this author+caption identity, or None.

        This is the pre-share check: a scan that recognises an open post here can refresh
        its counters without paying the share-sheet round trip for a URL it already holds.
        """
        if not post_ref:
            return None
        try:
            return self.query_one_orm_first(
                "SELECT * FROM social_posts WHERE platform = ? AND post_ref = ? "
                "ORDER BY last_scraped_at DESC LIMIT 1",
                (platform, post_ref),
            )
        except Exception as exc:
            logger.error(f"Error reading social post by ref {post_ref}: {exc}")
            return None

    def record(
        self,
        post_url: str,
        author_username: str,
        likes_count: Optional[int] = None,
        comments_count: Optional[int] = None,
        platform: str = 'instagram',
        post_type: Optional[str] = None,
        post_ref: Optional[str] = None,
        caption_preview: Optional[str] = None,
        posted_at_label: Optional[str] = None,
        grid_position: Optional[int] = None,
        scraping_id: Optional[int] = None,
    ) -> Optional[int]:
        """Store (or refresh) one post.

        Upsert on (platform, post_url) after normalising the URL, so every copy of a share
        link lands on the same row. A None counter never erases a known one (a read can
        fail on a post we already measured); `first_seen_at` is kept across refreshes.
        """
        url = canonical_post_url(post_url)
        author = (author_username or "").strip().lstrip("@").lower()
        if not url or not author:
            logger.warning(f"Social post not recorded: unusable url/author ({post_url!r}, {author_username!r})")
            return None
        preview = (caption_preview or "").strip()[:CAPTION_PREVIEW_MAX] or None
        try:
            cursor = self.execute(
                """INSERT INTO social_posts
                   (platform, sync_id, post_url, shortcode, post_type, author_username, post_ref,
                    caption_preview, likes_count, comments_count, posted_at_label, grid_position,
                    scraping_id, first_seen_at, last_scraped_at, updated_at)
                   VALUES (?, lower(hex(randomblob(16))), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'), datetime('now'))
                   ON CONFLICT(platform, post_url) DO UPDATE SET
                     post_type = COALESCE(excluded.post_type, post_type),
                     author_username = excluded.author_username,
                     post_ref = COALESCE(excluded.post_ref, post_ref),
                     caption_preview = COALESCE(excluded.caption_preview, caption_preview),
                     likes_count = COALESCE(excluded.likes_count, likes_count),
                     comments_count = COALESCE(excluded.comments_count, comments_count),
                     posted_at_label = COALESCE(excluded.posted_at_label, posted_at_label),
                     grid_position = COALESCE(excluded.grid_position, grid_position),
                     scraping_id = COALESCE(excluded.scraping_id, scraping_id),
                     last_scraped_at = excluded.last_scraped_at,
                     updated_at = excluded.updated_at""",
                (
                    platform, url, post_shortcode_from_url(url), post_type or post_type_from_url(url),
                    author, post_ref, preview, likes_count, comments_count, posted_at_label,
                    grid_position, scraping_id,
                ),
            )
            return cursor.lastrowid
        except Exception as exc:
            logger.error(f"Error recording social post {url}: {exc}")
            return None

    def refresh_counts_by_ref(
        self,
        post_ref: str,
        likes_count: Optional[int],
        comments_count: Optional[int],
        platform: str = 'instagram',
        scraping_id: Optional[int] = None,
    ) -> bool:
        """Refresh the counters of a post recognised by its author+caption identity.

        Used when a scan meets a post the catalogue already holds: the counters are the
        only thing that moved, and the URL is already known. True when a row was touched.
        """
        if not post_ref:
            return False
        try:
            cursor = self.execute(
                """UPDATE social_posts
                   SET likes_count = COALESCE(?, likes_count),
                       comments_count = COALESCE(?, comments_count),
                       scraping_id = COALESCE(?, scraping_id),
                       last_scraped_at = datetime('now'),
                       updated_at = datetime('now')
                   WHERE platform = ? AND post_ref = ?""",
                (likes_count, comments_count, scraping_id, platform, post_ref),
            )
            return (cursor.rowcount or 0) > 0
        except Exception as exc:
            logger.error(f"Error refreshing social post counts for {post_ref}: {exc}")
            return False

    def list_for_author(
        self, author_username: str, platform: str = 'instagram', limit: int = 50
    ) -> List[Dict[str, Any]]:
        """This author's catalogued posts, most liked first."""
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
            logger.error(f"Error listing social posts for {author}: {exc}")
            return []

    def top_posts(
        self,
        platform: str = 'instagram',
        author_username: Optional[str] = None,
        min_likes: int = 0,
        min_comments: int = 0,
        order_by: str = 'likes_count',
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """The posts worth a run: filtered by counters, biggest first.

        `order_by` is closed to the catalogue's counters/dates — it is interpolated.
        """
        if order_by not in _ORDERABLE_COLUMNS:
            raise ValueError(f"Unsupported order column: {order_by!r}")
        where = ["platform = ?", "COALESCE(likes_count, 0) >= ?", "COALESCE(comments_count, 0) >= ?"]
        params: List[Any] = [platform, int(min_likes), int(min_comments)]
        author = (author_username or "").strip().lstrip("@").lower()
        if author:
            where.append("author_username = ?")
            params.append(author)
        params.append(int(limit))
        try:
            return self.query_orm_first(
                f"SELECT * FROM social_posts WHERE {' AND '.join(where)} "
                f"ORDER BY {order_by} DESC, last_scraped_at DESC LIMIT ?",
                tuple(params),
            )
        except Exception as exc:
            logger.error(f"Error listing top social posts: {exc}")
            return []

    def count_for_author(self, author_username: str, platform: str = 'instagram') -> int:
        """How many of this author's posts the catalogue holds."""
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
            logger.error(f"Error counting social posts for {author}: {exc}")
            return 0
