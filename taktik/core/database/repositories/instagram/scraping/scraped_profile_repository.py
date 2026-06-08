"""Repository for Instagram scraped profile junction rows and AI scoring."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from ..._base.base_repository import BaseRepository


class ScrapedProfileRepository(BaseRepository):
    """Data access for scraped_profiles."""

    def link_profile_to_session(
        self,
        scraping_id: int,
        profile_id: int,
        source_post_url: Optional[str] = None,
    ) -> bool:
        """Link a profile to a scraping session."""
        try:
            self.execute(
                """
                INSERT INTO scraped_profiles (platform, scraping_id, profile_id, source_post_url)
                VALUES ('instagram', ?, ?, ?)
                ON CONFLICT(scraping_id, profile_id)
                DO UPDATE SET source_post_url = COALESCE(excluded.source_post_url, source_post_url)
                """,
                (scraping_id, profile_id, source_post_url),
            )
            return True
        except Exception as exc:
            logger.debug(f"Error linking profile {profile_id} to session {scraping_id}: {exc}")
            return False

    def link_profiles_to_session(self, scraping_id: int, profile_ids: List[int]) -> int:
        """Link multiple profiles to a scraping session."""
        if not profile_ids:
            return 0

        linked = 0
        for profile_id in profile_ids:
            try:
                cursor = self.execute(
                    "INSERT OR IGNORE INTO scraped_profiles (platform, scraping_id, profile_id) VALUES ('instagram', ?, ?)",
                    (scraping_id, profile_id),
                )
                if cursor.rowcount > 0:
                    linked += 1
            except Exception:
                pass
        return linked

    def get_scraped_profiles(self, scraping_id: int) -> List[Dict[str, Any]]:
        """Get profiles for a scraping session with details (ORM-first, fallback raw)."""
        rows = self.query_orm_first(
            """
            SELECT
                sp.id, sp.scraping_id, sp.profile_id, sp.scraped_at, sp.source_post_url,
                sp.ai_score, sp.ai_qualified, sp.ai_analysis,
                sp.qualification_criteria, sp.scored_at,
                ip.username, ip.full_name, ip.biography,
                ip.followers_count, ip.following_count, ip.posts_count,
                ip.is_private, ip.is_verified, ip.is_business, ip.business_category
            FROM scraped_profiles sp
            JOIN instagram_profiles ip ON sp.profile_id = ip.profile_id
            WHERE sp.scraping_id = ?
            ORDER BY sp.ai_score DESC NULLS LAST, sp.scraped_at DESC
            """,
            (scraping_id,),
        )
        return [self._map_scraped_profile_row(row) for row in rows]

    def update_ai_scores(
        self,
        scraping_id: int,
        scores: List[Dict[str, Any]],
        qualification_criteria: str,
    ) -> int:
        """Update AI scores for scraped profiles."""
        updated = 0
        for score in scores:
            cursor = self.execute(
                """
                UPDATE scraped_profiles
                SET ai_score = ?, ai_qualified = ?, ai_analysis = ?,
                    qualification_criteria = ?, scored_at = datetime('now')
                WHERE scraping_id = ? AND profile_id = ?
                """,
                (
                    score.get("ai_score") if score.get("ai_score") is not None else score.get("aiScore"),
                    1 if (score.get("ai_qualified") or score.get("aiQualified")) else 0,
                    score.get("ai_analysis") or score.get("aiAnalysis"),
                    qualification_criteria,
                    scraping_id,
                    score.get("profile_id") or score.get("profileId"),
                ),
            )
            if cursor.rowcount > 0:
                updated += 1

        logger.debug(f"Updated AI scores for {updated} scraped profiles")
        return updated

    def update_scraped_profile_ai(
        self,
        scraping_id: int,
        profile_id: int,
        ai_score: Optional[int],
        ai_qualified: bool,
        ai_analysis: str = "",
    ) -> bool:
        """Update AI qualification columns for one scraped profile."""
        try:
            cursor = self.execute(
                """
                UPDATE scraped_profiles
                SET ai_score = ?, ai_qualified = ?, ai_analysis = ?
                WHERE scraping_id = ? AND profile_id = ?
                """,
                (ai_score, 1 if ai_qualified else 0, ai_analysis, scraping_id, profile_id),
            )
            return cursor.rowcount > 0
        except Exception as exc:
            logger.debug(f"Error updating AI score for profile {profile_id} / session {scraping_id}: {exc}")
            return False

    def get_qualified_profiles(self, scraping_id: int, min_score: int = 60) -> List[Dict[str, Any]]:
        """Get qualified profiles for a scraping session (ORM-first, fallback raw)."""
        rows = self.query_orm_first(
            """
            SELECT sp.*, ip.username, ip.full_name, ip.biography,
                ip.followers_count, ip.following_count, ip.posts_count,
                ip.is_private, ip.is_verified, ip.is_business, ip.business_category
            FROM scraped_profiles sp
            JOIN instagram_profiles ip ON sp.profile_id = ip.profile_id
            WHERE sp.scraping_id = ? AND sp.ai_qualified = 1 AND sp.ai_score >= ?
            ORDER BY sp.ai_score DESC
            """,
            (scraping_id, min_score),
        )
        return [self._map_scraped_profile_row(row) for row in rows]

    def count_by_qualification(self, scraping_id: int) -> Dict[str, int]:
        """Count profiles by qualification status (ORM-first, fallback raw)."""
        row = self.query_one_orm_first(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN ai_qualified = 1 THEN 1 ELSE 0 END) as qualified,
                SUM(CASE WHEN ai_qualified = 0 AND ai_score IS NOT NULL THEN 1 ELSE 0 END) as not_qualified,
                SUM(CASE WHEN ai_score IS NULL THEN 1 ELSE 0 END) as not_scored
            FROM scraped_profiles
            WHERE scraping_id = ?
            """,
            (scraping_id,),
        )

        return {
            "total": row["total"] if row else 0,
            "qualified": row["qualified"] if row else 0,
            "not_qualified": row["not_qualified"] if row else 0,
            "not_scored": row["not_scored"] if row else 0,
        }

    def is_post_url_already_scraped(self, post_url: str) -> bool:
        """Return True when a post URL already produced scraped profiles."""
        if not post_url:
            return False
        row = self.query_one(
            "SELECT 1 FROM scraped_profiles WHERE source_post_url = ? LIMIT 1",
            (post_url,),
        )
        return row is not None

    def _map_scraped_profile_row(self, row) -> Dict[str, Any]:
        row_dict = dict(row)
        return {
            **row_dict,
            "ai_qualified": bool(row_dict.get("ai_qualified", 0)),
            "is_private": bool(row_dict.get("is_private", 0)),
            "is_verified": bool(row_dict.get("is_verified", 0)),
            "is_business": bool(row_dict.get("is_business", 0)),
        }
