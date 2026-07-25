"""Facade for recording the comments we post on other people's content.

Keeps the comment ACTION free of SQL: it calls one function with what it knows, and the
ownership of the `posted_comments` table stays in `taktik/core/database/**`
(repositories/instagram/posted_comment). Mirrors the InstagramWorkflowStateService style.

Never raises: the comment is already live on the platform by the time we get here, so a
bookkeeping failure must never surface as a workflow error.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

# Post identity is shared with the analysis cache — single owner, re-exported here for the
# callers that already imported it from this module.
from taktik.core.database.instagram_post_identity import build_post_ref


class InstagramPostedComments:
    """Write-side facade for `posted_comments`."""

    @staticmethod
    def _db():
        from taktik.core.database.local.service import LocalDatabaseService
        return LocalDatabaseService()

    @staticmethod
    def record(
        target_username: str,
        comment_text: str,
        account_id: Optional[int] = None,
        session_id: Optional[int] = None,
        ai_metadata: Optional[Dict[str, Any]] = None,
        source: str = "template",
        posted_at: Optional[str] = None,
        kind: str = "comment",
        reply_to_username: Optional[str] = None,
        reply_to_text: Optional[str] = None,
    ) -> Optional[int]:
        """Store one posted comment; returns its row id (or None).

        `ai_metadata` is what the AI hook knows and the action does not: which model wrote
        the comment, what the call cost, the model's own reasoning, the post caption/vision
        description and the language. Absent for template/custom comments.

        `kind='reply'` is an answer to someone's comment under a post: `target_username` is
        then the COMMENTER, and `reply_to_*` keeps whom we answered and what they wrote.
        """
        if not target_username or not comment_text:
            return None
        meta = ai_metadata or {}
        try:
            post_author = meta.get("post_author") or target_username
            post_caption = meta.get("post_caption")
            return InstagramPostedComments._db().posted_comments.record(
                target_username=target_username,
                comment_text=comment_text,
                account_id=account_id,
                session_id=session_id,
                platform="instagram",
                post_author=post_author,
                post_ref=build_post_ref(post_author, post_caption),
                post_url=meta.get("post_url"),
                post_caption=post_caption,
                post_description=meta.get("post_description"),
                source=source,
                ai_model=meta.get("model"),
                ai_cost_usd=meta.get("cost_usd"),
                ai_reasoning=meta.get("reasoning"),
                language=meta.get("language"),
                posted_at=posted_at,
                kind=kind,
                reply_to_username=reply_to_username,
                reply_to_text=reply_to_text,
            )
        except Exception as exc:
            logger.warning(f"Could not record posted comment for @{target_username}: {exc}")
            return None

    @staticmethod
    def attach_post_url(comment_id: int, post_url: str) -> bool:
        """Complete a stored comment with the shareable link, once captured."""
        if not comment_id or not post_url:
            return False
        try:
            return InstagramPostedComments._db().posted_comments.attach_post_url(comment_id, post_url)
        except Exception as exc:
            logger.warning(f"Could not attach post URL to comment {comment_id}: {exc}")
            return False


__all__ = ["InstagramPostedComments", "build_post_ref"]
