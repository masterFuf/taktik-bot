"""
Post-analysis repository — the reusable facts of a post's AI analysis.

Owner of the `post_analysis` table (see local/schemas/post_analysis.py for why only the
FACTS are stored and never the per-account verdict). Bot is the source of truth.
"""

from typing import Any, Dict, Optional

from loguru import logger

from ..._base.base_repository import BaseRepository


class PostAnalysisRepository(BaseRepository):
    """Repository for the post-analysis reuse cache."""

    def find_by_ref(self, post_ref: str, platform: str = 'instagram') -> Optional[Dict[str, Any]]:
        """The stored analysis for this post, or None. Read-only (no hit bookkeeping)."""
        if not post_ref:
            return None
        try:
            return self.query_one_orm_first(
                "SELECT * FROM post_analysis WHERE platform = ? AND post_ref = ?",
                (platform, post_ref),
            )
        except Exception as exc:
            logger.error(f"Error reading post analysis for {post_ref}: {exc}")
            return None

    def record(
        self,
        post_ref: str,
        description: Optional[str] = None,
        platform: str = 'instagram',
        post_author: Optional[str] = None,
        post_caption: Optional[str] = None,
        post_language: Optional[str] = None,
        ai_model: Optional[str] = None,
        ai_cost_usd: Optional[float] = None,
    ) -> Optional[int]:
        """Store (or refresh) the analysis of one post.

        Upsert on (platform, post_ref): re-analysing a post we already knew — which happens
        when the cache was skipped, e.g. a caption too weak to key on — must not raise on the
        UNIQUE constraint. `hit_count` is deliberately preserved across a refresh.
        """
        if not post_ref:
            return None
        try:
            cursor = self.execute(
                """INSERT INTO post_analysis
                   (platform, sync_id, post_ref, post_author, post_caption, description,
                    post_language, ai_model, ai_cost_usd, analyzed_at, created_at)
                   VALUES (?, lower(hex(randomblob(16))), ?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), datetime('now'))
                   ON CONFLICT(platform, post_ref) DO UPDATE SET
                     post_author = excluded.post_author,
                     post_caption = excluded.post_caption,
                     description = excluded.description,
                     post_language = excluded.post_language,
                     ai_model = excluded.ai_model,
                     ai_cost_usd = excluded.ai_cost_usd,
                     analyzed_at = excluded.analyzed_at""",
                (
                    platform, post_ref, post_author, post_caption, description,
                    post_language, ai_model, ai_cost_usd,
                ),
            )
            return cursor.lastrowid
        except Exception as exc:
            logger.error(f"Error recording post analysis for {post_ref}: {exc}")
            return None

    def mark_reused(self, post_ref: str, platform: str = 'instagram') -> bool:
        """Count one reuse of this analysis (what makes the saving measurable)."""
        if not post_ref:
            return False
        try:
            self.execute(
                """UPDATE post_analysis
                   SET hit_count = COALESCE(hit_count, 0) + 1, last_used_at = datetime('now')
                   WHERE platform = ? AND post_ref = ?""",
                (platform, post_ref),
            )
            return True
        except Exception as exc:
            logger.error(f"Error marking post analysis reuse for {post_ref}: {exc}")
            return False

    def savings_summary(self, platform: str = 'instagram') -> Dict[str, Any]:
        """How much the cache has actually saved: reuses x what each analysis cost."""
        try:
            row = self.query_one_orm_first(
                """SELECT COUNT(*) AS analyses,
                          COALESCE(SUM(hit_count), 0) AS reuses,
                          COALESCE(SUM(COALESCE(hit_count, 0) * COALESCE(ai_cost_usd, 0)), 0) AS saved_usd
                   FROM post_analysis WHERE platform = ?""",
                (platform,),
            )
            return row or {"analyses": 0, "reuses": 0, "saved_usd": 0}
        except Exception as exc:
            logger.error(f"Error computing post analysis savings: {exc}")
            return {"analyses": 0, "reuses": 0, "saved_usd": 0}
