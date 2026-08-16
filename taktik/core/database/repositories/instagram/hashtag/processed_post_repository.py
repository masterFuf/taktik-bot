"""Which hashtag posts this account has already worked.

Owns `processed_hashtag_posts`: the memory that stops a hashtag run from re-opening a post
it already mined, and the record of what that pass produced.

The SQL lived inline in `LocalDatabaseService`, where the hashtag normalisation was spelled
out at each of the four call sites — the kind of repetition that ends with one site
forgetting the `#` and silently never matching anything again. It is applied once here, on
the way in and on the way out.
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from ..._base.base_repository import BaseRepository


# A hashtag is stored bare and lowercased. Reads and writes MUST fold the same way: a row
# written as "paris" is invisible to a lookup for "#Paris".
def normalize_hashtag(hashtag: str) -> str:
    return (hashtag or "").lower().strip("#")


class ProcessedHashtagPostRepository(BaseRepository):
    """Posts already processed during hashtag runs."""

    def is_processed(
        self,
        account_id: int,
        hashtag: str,
        post_author: str,
        post_caption_hash: Optional[str] = None,
        hours_limit: int = 168,  # 7 days
    ) -> bool:
        """Has this post already been worked within the window?

        With a caption hash the match is on the exact post; without one it falls back to
        author + hashtag, which is deliberately broader — re-opening the same author's post
        twice in a week costs a visit, and the fallback only runs when the caption could
        not be read.
        """
        try:
            tag = normalize_hashtag(hashtag)
            if post_caption_hash:
                row = self.query_one(
                    """
                    SELECT id FROM processed_hashtag_posts
                    WHERE account_id = ?
                    AND hashtag = ?
                    AND post_author = ?
                    AND post_caption_hash = ?
                    AND processed_at >= datetime('now', '-' || ? || ' hours')
                    """,
                    (account_id, tag, post_author, post_caption_hash, hours_limit),
                )
            else:
                row = self.query_one(
                    """
                    SELECT id FROM processed_hashtag_posts
                    WHERE account_id = ?
                    AND hashtag = ?
                    AND post_author = ?
                    AND processed_at >= datetime('now', '-' || ? || ' hours')
                    """,
                    (account_id, tag, post_author, hours_limit),
                )
            return row is not None
        except Exception as exc:
            # A memory that cannot answer must not stop a run: treat the post as unseen and
            # work it. Worst case we spend one visit twice.
            logger.error(f"Error checking processed hashtag post: {exc}")
            return False

    def record(
        self,
        account_id: int,
        hashtag: str,
        post_author: str,
        post_caption_hash: Optional[str] = None,
        post_caption_preview: Optional[str] = None,
        likes_count: Optional[int] = None,
        comments_count: Optional[int] = None,
        likers_processed: int = 0,
        interactions_made: int = 0,
    ) -> bool:
        """Record a post as processed, with what the pass produced."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO processed_hashtag_posts
                (account_id, hashtag, post_author, post_caption_hash, post_caption_preview,
                 likes_count, comments_count, likers_processed, interactions_made, processed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    account_id,
                    normalize_hashtag(hashtag),
                    post_author,
                    post_caption_hash,
                    post_caption_preview[:100] if post_caption_preview else None,
                    likes_count,
                    comments_count,
                    likers_processed,
                    interactions_made,
                ),
            )
            self.conn.commit()
            logger.debug(f"Recorded processed hashtag post: #{hashtag} by @{post_author}")
            return True
        except Exception as exc:
            logger.error(f"Error recording processed hashtag post: {exc}")
            return False

    def list_for_account(
        self,
        account_id: int,
        hashtag: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Most recently processed posts, optionally narrowed to one hashtag."""
        try:
            if hashtag:
                rows = self.query(
                    """
                    SELECT * FROM processed_hashtag_posts
                    WHERE account_id = ? AND hashtag = ?
                    ORDER BY processed_at DESC LIMIT ?
                    """,
                    (account_id, normalize_hashtag(hashtag), limit),
                )
            else:
                rows = self.query(
                    """
                    SELECT * FROM processed_hashtag_posts
                    WHERE account_id = ?
                    ORDER BY processed_at DESC LIMIT ?
                    """,
                    (account_id, limit),
                )
            return [dict(row) for row in rows]
        except Exception as exc:
            logger.error(f"Error getting processed hashtag posts: {exc}")
            return []


__all__ = ["ProcessedHashtagPostRepository", "normalize_hashtag"]
