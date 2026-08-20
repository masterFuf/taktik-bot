"""
Posted-comment repository — the comments WE leave on other people's content.

Owner of the `posted_comments` table (see local/schemas/posted_comments.py for why it
is separate from both `interactions` and `smart_comment_replies`). Bot is the source of
truth: it writes as each comment lands; Electron reads for the session drill-down.
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from ..._base.base_repository import BaseRepository


class PostedCommentRepository(BaseRepository):
    """Repository for comments posted by our accounts."""

    def record(
        self,
        target_username: str,
        comment_text: str,
        account_id: Optional[int] = None,
        session_id: Optional[int] = None,
        platform: str = 'instagram',
        post_author: Optional[str] = None,
        post_ref: Optional[str] = None,
        post_url: Optional[str] = None,
        post_caption: Optional[str] = None,
        post_description: Optional[str] = None,
        source: str = 'ai',
        ai_model: Optional[str] = None,
        ai_cost_usd: Optional[float] = None,
        ai_reasoning: Optional[str] = None,
        language: Optional[str] = None,
        posted_at: Optional[str] = None,
        kind: str = 'comment',
        reply_to_username: Optional[str] = None,
        reply_to_text: Optional[str] = None,
    ) -> Optional[int]:
        """Store one posted comment. Returns the row id, or None on failure.

        `kind='reply'` records an answer to someone's comment under a post: `target_username`
        is then the COMMENTER we address, and `reply_to_*` keeps whom we answered and what
        they had written.

        Never raises: a bookkeeping failure must not cost us a comment that is already
        live on the platform. `posted_at` takes the real moment of the gesture when the
        caller has it; NULL falls back to the insert time.
        """
        try:
            cursor = self.execute(
                """INSERT INTO posted_comments
                   (platform, sync_id, account_id, session_id, target_username, post_author,
                    post_ref, post_url, post_caption, post_description, comment_text, source,
                    ai_model, ai_cost_usd, ai_reasoning, language, posted_at, created_at,
                    kind, reply_to_username, reply_to_text)
                   VALUES (?, lower(hex(randomblob(16))), ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, COALESCE(?, datetime('now')), datetime('now'),
                           ?, ?, ?)""",
                (
                    platform, account_id, session_id, target_username, post_author,
                    post_ref, post_url, post_caption, post_description, comment_text, source,
                    ai_model, ai_cost_usd, ai_reasoning, language, posted_at,
                    kind or 'comment', reply_to_username, reply_to_text,
                ),
            )
            return cursor.lastrowid
        except Exception as exc:
            logger.error(f"Error recording posted comment for @{target_username}: {exc}")
            return None

    def get_by_session(self, session_id: int, platform: str = 'instagram') -> List[Dict[str, Any]]:
        """Every comment posted during one session, most recent first."""
        try:
            return self.query_orm_first(
                """SELECT * FROM posted_comments
                   WHERE session_id = ? AND platform = ?
                   ORDER BY posted_at DESC""",
                (session_id, platform),
            )
        except Exception as exc:
            logger.error(f"Error reading posted comments for session {session_id}: {exc}")
            return []

    def get_by_target(
        self, target_username: str, platform: str = 'instagram', limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Comment history for one profile — "what have we already said to them?"."""
        try:
            return self.query_orm_first(
                """SELECT * FROM posted_comments
                   WHERE target_username = ? AND platform = ?
                   ORDER BY posted_at DESC LIMIT ?""",
                (target_username, platform, limit),
            )
        except Exception as exc:
            logger.error(f"Error reading posted comments for @{target_username}: {exc}")
            return []

    def recent_texts(
        self,
        account_id: Optional[int] = None,
        platform: str = 'instagram',
        limit: int = 12,
        kind: str = 'comment',
    ) -> List[str]:
        """The account's latest published comment texts, newest first.

        Feeds the generation-side anti-tic guard: the model is shown what THIS account just
        published so it stops repeating its own openers and emoji. Scoped to one account when
        `account_id` is known — another account's voice is not this account's tic — and to
        AI-written comments (a template repeating is the operator's choice, not a tic).
        """
        try:
            where = "platform = ? AND kind = ? AND source = 'ai'"
            params: list = [platform, kind]
            if account_id is not None:
                where += " AND account_id = ?"
                params.append(account_id)
            rows = self.query_orm_first(
                f"""SELECT comment_text FROM posted_comments
                    WHERE {where}
                    ORDER BY posted_at DESC LIMIT ?""",
                (*params, limit),
            )
            return [r['comment_text'] for r in rows if r.get('comment_text')]
        except Exception as exc:
            logger.error(f"Error reading recent posted comments: {exc}")
            return []

    def attach_post_url(self, comment_id: int, post_url: str) -> bool:
        """Fill in the shareable post link after the fact.

        The link is captured AFTER the comment is posted (it costs a share-sheet round
        trip), so the row is written first and completed here only if that succeeds.
        """
        try:
            self.execute(
                "UPDATE posted_comments SET post_url = ? WHERE id = ?",
                (post_url, comment_id),
            )
            return True
        except Exception as exc:
            logger.error(f"Error attaching post URL to comment {comment_id}: {exc}")
            return False
