"""Facade for reusing a post's AI analysis instead of re-paying for it.

Keeps the AI hook free of SQL, and keeps the reuse RULE in one place: a post analysis is
only cacheable when its caption identifies the post well enough (see
instagram_post_identity). A cache miss just costs the call we would have made anyway; a
wrong hit would describe the wrong post — so the rule fails closed.

Only the FACTS are reused (what the post shows, its language). The per-account verdict is
never stored, cf. local/schemas/post_analysis.py.

Never raises: a caching failure must never cost a run.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

from taktik.core.database.instagram_post_identity import (
    build_post_ref,
    is_discriminating_post_ref,
)


class InstagramPostAnalysis:
    """Read/write side of the post-analysis reuse cache."""

    @staticmethod
    def _db():
        # Le SINGLETON, pas une instance neuve. Construire le service rejoue TOUTE la suite de
        # migrations et rebatit le moteur SQLAlchemy : 56 ms mesurees, et surtout un verrou
        # d'ecriture sur une base partagee avec Electron et le renderer. Vu dans un log de run
        # reel : un commentaire poste declenchait une reinitialisation complete de la base, deux
        # fois — une pour `record`, une pour `attach_post_url`.
        from taktik.core.database.local.service import get_local_database

        return get_local_database()

    @staticmethod
    def cache_key(post_author: Optional[str], post_caption: Optional[str]) -> Optional[str]:
        """The ref to cache this post under, or None when it cannot be keyed safely."""
        if not is_discriminating_post_ref(post_caption):
            return None
        return build_post_ref(post_author, post_caption)

    @staticmethod
    def load(post_author: Optional[str], post_caption: Optional[str]) -> Optional[Dict[str, Any]]:
        """A previously stored analysis of THIS post, or None.

        Returns None (never raises) when the post cannot be keyed, when nothing is stored,
        or when the stored row carries no description — all of which mean "just analyse it".
        """
        ref = InstagramPostAnalysis.cache_key(post_author, post_caption)
        if not ref:
            return None
        try:
            row = InstagramPostAnalysis._db().post_analysis.find_by_ref(ref)
        except Exception as exc:
            logger.debug(f"Post analysis lookup failed for {ref}: {exc}")
            return None
        if not row or not (row.get("description") or "").strip():
            return None
        return row

    @staticmethod
    def mark_reused(post_author: Optional[str], post_caption: Optional[str]) -> None:
        """Count one reuse, so the saving is measurable rather than assumed."""
        ref = InstagramPostAnalysis.cache_key(post_author, post_caption)
        if not ref:
            return
        try:
            InstagramPostAnalysis._db().post_analysis.mark_reused(ref)
        except Exception as exc:
            logger.debug(f"Post analysis reuse bookkeeping failed for {ref}: {exc}")

    @staticmethod
    def store(
        post_author: Optional[str],
        post_caption: Optional[str],
        description: Optional[str],
        post_language: Optional[str] = None,
        ai_model: Optional[str] = None,
        ai_cost_usd: Optional[float] = None,
    ) -> Optional[int]:
        """Store the facts of a fresh analysis, when the post can be keyed safely."""
        ref = InstagramPostAnalysis.cache_key(post_author, post_caption)
        if not ref or not (description or "").strip():
            return None
        try:
            return InstagramPostAnalysis._db().post_analysis.record(
                post_ref=ref,
                description=description,
                post_author=post_author,
                post_caption=post_caption,
                post_language=post_language,
                ai_model=ai_model,
                ai_cost_usd=ai_cost_usd,
            )
        except Exception as exc:
            logger.warning(f"Could not store post analysis for {ref}: {exc}")
            return None


__all__ = ["InstagramPostAnalysis"]
