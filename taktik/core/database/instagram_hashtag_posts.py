"""Database-owned helpers for processed Instagram hashtag posts.

This facade absorbs the legacy hashtag post bookkeeping that used to live in
`social_media/instagram/.../database_helpers.py`:

- detect whether a hashtag post was already processed
- persist the processed-post marker
- compute the stable caption hash used as part of the dedup key

The persistence path still goes through `LocalDatabaseService` for now because
that is where the existing `processed_hashtag_posts` API lives. The ownership of
the decision is nevertheless moved into the database layer so workflows stop
defining DB behavior inside the platform package.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from loguru import logger

log = logger.bind(module="database-instagram-hashtag-posts")


class InstagramHashtagPostService:
    """Database facade for processed hashtag post bookkeeping."""

    @staticmethod
    def _local_db():
        from taktik.core.database.local.service import get_local_database

        return get_local_database()

    @staticmethod
    def is_processed(
        hashtag: str,
        post_author: str,
        post_caption_hash: Optional[str] = None,
        account_id: Optional[int] = None,
        hours_limit: int = 168,
    ) -> bool:
        if not account_id:
            return False

        try:
            is_processed = InstagramHashtagPostService._local_db().is_hashtag_post_processed(
                account_id=account_id,
                hashtag=hashtag,
                post_author=post_author,
                post_caption_hash=post_caption_hash,
                hours_limit=hours_limit,
            )

            if is_processed:
                log.debug("Post #{} by @{} already processed", hashtag, post_author)

            return is_processed
        except Exception as exc:
            log.error("Error checking hashtag post #{} / @{}: {}", hashtag, post_author, exc)
            return False

    @staticmethod
    def record_processed(
        hashtag: str,
        post_author: str,
        post_caption_hash: Optional[str] = None,
        post_caption_preview: Optional[str] = None,
        likes_count: Optional[int] = None,
        comments_count: Optional[int] = None,
        likers_processed: int = 0,
        interactions_made: int = 0,
        account_id: Optional[int] = None,
    ) -> bool:
        if not account_id:
            log.warning("account_id missing - cannot record processed hashtag post")
            return False

        try:
            success = InstagramHashtagPostService._local_db().record_processed_hashtag_post(
                account_id=account_id,
                hashtag=hashtag,
                post_author=post_author,
                post_caption_hash=post_caption_hash,
                post_caption_preview=post_caption_preview,
                likes_count=likes_count,
                comments_count=comments_count,
                likers_processed=likers_processed,
                interactions_made=interactions_made,
            )

            if success:
                log.debug("Processed hashtag post recorded: #{} by @{}", hashtag, post_author)

            return success
        except Exception as exc:
            log.error("Error recording hashtag post #{} / @{}: {}", hashtag, post_author, exc)
            return False

    @staticmethod
    def generate_caption_hash(caption: str) -> str:
        """Generate the dedup hash used by processed hashtag posts."""
        if not caption:
            return "empty"

        normalized = caption.lower().strip()[:100]
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


__all__ = ["InstagramHashtagPostService"]
