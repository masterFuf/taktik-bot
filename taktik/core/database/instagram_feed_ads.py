"""Database facade for the sponsored creatives met while browsing a feed.

One row per CREATIVE, never per encounter: `record_sighting` upserts on the perceptual
hash, so meeting the same ad again only bumps `times_seen` and `last_seen_at`. That counter
is the whole point — a creative seen forty times over three weeks is an advertiser whose
budget is holding, which is the one signal a competitor cannot fake.

It also bounds the AI bill: `pending_analysis()` returns creatives, not sightings, so an
account that meets five hundred ads may only ever pay for sixty analyses.

Never raises. Collecting market intelligence is a side effect of a run; it must never be
able to cost the run it rides in on.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from loguru import logger

log = logger.bind(module="database-instagram-feed-ads")


class InstagramFeedAdsService:
    """Read/write side of the sponsored-creative corpus."""

    @staticmethod
    def _db():
        from taktik.core.database.local.service import get_local_database

        return get_local_database()

    @staticmethod
    def record_sighting(
        *,
        creative_hash: str,
        advertiser: Optional[str] = None,
        account_id: Optional[int] = None,
        screenshot: Optional[bytes] = None,
        ocr_text: Optional[str] = None,
        platform: str = "instagram",
    ) -> Optional[int]:
        """Record one encounter. Returns the creative's row id, or ``None`` on failure.

        A known creative is NOT rewritten: the screenshot and OCR of the first sighting are
        kept, because re-storing a blob on every encounter would grow the file for no new
        information. Only the counter and the last-seen date move.
        """
        if not creative_hash:
            return None
        try:
            conn = InstagramFeedAdsService._db()._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO feed_ads
                    (creative_hash, advertiser, account_id, platform, screenshot, ocr_text)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(creative_hash) DO UPDATE SET
                    times_seen = times_seen + 1,
                    last_seen_at = datetime('now'),
                    -- Fill in what the first sighting could not read, without ever
                    -- overwriting what it did.
                    advertiser = COALESCE(feed_ads.advertiser, excluded.advertiser),
                    ocr_text   = COALESCE(feed_ads.ocr_text, excluded.ocr_text),
                    screenshot = COALESCE(feed_ads.screenshot, excluded.screenshot)
                """,
                (creative_hash, advertiser, account_id, platform, screenshot, ocr_text),
            )
            conn.commit()
            cursor.execute("SELECT id FROM feed_ads WHERE creative_hash = ?", (creative_hash,))
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as exc:
            log.debug(f"Could not record ad sighting: {exc}")
            return None

    @staticmethod
    def top_creatives(limit: int = 50, platform: str = "instagram") -> List[Dict[str, Any]]:
        """The creatives that keep coming back, most-seen first — the corpus's main read."""
        try:
            conn = InstagramFeedAdsService._db()._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, creative_hash, advertiser, times_seen, ocr_text,
                       ai_analysis, first_seen_at, last_seen_at
                FROM feed_ads
                WHERE platform = ?
                ORDER BY times_seen DESC, last_seen_at DESC
                LIMIT ?
                """,
                (platform, limit),
            )
            columns = [c[0] for c in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as exc:
            log.debug(f"Could not read top creatives: {exc}")
            return []

    @staticmethod
    def pending_analysis(limit: int = 20, platform: str = "instagram") -> List[Dict[str, Any]]:
        """Creatives still waiting for their AI pass, most-seen first.

        Most-seen first on purpose: if the budget only allows a few analyses, they should go
        to the ads that are actually running, not to a one-off impression.
        """
        try:
            conn = InstagramFeedAdsService._db()._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, creative_hash, advertiser, times_seen, ocr_text, screenshot
                FROM feed_ads
                WHERE platform = ? AND ai_analyzed_at IS NULL
                ORDER BY times_seen DESC
                LIMIT ?
                """,
                (platform, limit),
            )
            columns = [c[0] for c in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as exc:
            log.debug(f"Could not read pending analyses: {exc}")
            return []

    @staticmethod
    def save_analysis(creative_id: int, analysis: Dict[str, Any]) -> bool:
        """Attach an AI analysis to a creative. Stamped even when the analysis is empty, so
        a creative the model could not read is not retried forever."""
        try:
            conn = InstagramFeedAdsService._db()._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE feed_ads SET ai_analysis = ?, ai_analyzed_at = datetime('now') "
                "WHERE id = ?",
                (json.dumps(analysis or {}, ensure_ascii=False), creative_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as exc:
            log.debug(f"Could not save ad analysis: {exc}")
            return False
