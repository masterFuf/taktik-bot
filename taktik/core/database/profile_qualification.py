"""Is this profile already AI-qualified, and with what? One answer, one place.

A profile's niche is a FACT about that profile, not about the account looking at it. So a
classification paid for once — by any account, in any workflow, on any day — is reusable by
every later pass. This facade is the single gate that decides it, so the Instagram
interaction hook, the scraping deep-qualify and (later) TikTok all agree on what "already
classified" means instead of each carrying its own inline test.

Sibling of `instagram_post_analysis.py`, same contract: it never raises. A lookup failure
means "we don't know", which costs the classification we would have made anyway; it must
never cost a run.

Two rules live here because both were learned the expensive way:

  - **The flag is not the answer.** `profile_qualification.has_ai = 1` is set on 19 039 of
    40 353 rows that carry no niche, no sub-niche and no profession. Reusing on the flag
    alone would hand the interaction engine an empty qualification and skip the vision call
    that was actually needed. A row counts only when it carries a real value.
  - **The lookup is by username.** See `repositories/instagram/profile_ai_read_model.py`:
    profile_id is not unique in the qualification store and joining on it serves one
    profile's niche for another's.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from loguru import logger

# Platforms whose profiles this facade can answer for.
#
# TikTok joined on 2026-08-29, but NOT by adding a word to this tuple. The Instagram path reads
# `FROM instagram_profiles` and joins `scraped_profiles WHERE platform = 'instagram'`: it is
# Instagram-only by construction, so widening the tuple alone would have served an Instagram
# namesake's niche for a TikTok handle — the exact confusion this module's header warns about.
# Each platform therefore brings its own reader; the tuple only says which ones have one.
SUPPORTED_PLATFORMS = ("instagram", "tiktok")


class ProfileQualification:
    """Read side of the AI qualification reuse gate."""

    @staticmethod
    def _db():
        from taktik.core.database.local.service import get_local_database

        return get_local_database()

    @staticmethod
    def _is_classified(row: Dict[str, Any]) -> bool:
        """Whether this row carries an actual classification, not just the `has_ai` flag."""
        return any(
            (row.get("niche_category"), row.get("niche"), row.get("profession"))
        )

    @staticmethod
    def _decode(row: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise one stored row into the shape every consumer expects.

        `profession_tags` is stored as a JSON string and `analysis_json` holds the fields the
        columns don't carry (tags, summary, following_insights). Decoding them here is what
        lets the text-only engagement verdict judge a cached profile on the same evidence the
        vision call had — it used to receive only the niche and the bio.
        """
        decoded = dict(row)

        raw_tags = decoded.get("profession_tags")
        if isinstance(raw_tags, str):
            try:
                raw_tags = json.loads(raw_tags)
            except (ValueError, TypeError):
                raw_tags = []
        decoded["profession_tags"] = raw_tags if isinstance(raw_tags, list) else []

        analysis: Dict[str, Any] = {}
        raw_analysis = decoded.pop("analysis_json", None)
        if isinstance(raw_analysis, str) and raw_analysis.strip():
            try:
                parsed = json.loads(raw_analysis)
                if isinstance(parsed, dict):
                    analysis = parsed
            except (ValueError, TypeError):
                analysis = {}

        tags = analysis.get("tags")
        decoded["tags"] = tags if isinstance(tags, list) else []
        decoded["summary"] = analysis.get("summary") or ""
        insights = analysis.get("following_insights")
        # The model returns [] when it had no following sample — keep the string contract.
        decoded["following_insights"] = insights if isinstance(insights, str) else ""
        decoded["gender"] = analysis.get("gender") or ""
        decoded["age_group"] = analysis.get("age_group") or ""
        decoded["country"] = analysis.get("country") or ""

        return decoded

    @staticmethod
    def _tiktok_rows(usernames: List[str]) -> List[Dict[str, Any]]:
        """TikTok qualifications, read straight from the store on (platform, username).

        Deliberately not the Instagram query: that one reads the `instagram_profiles` view and
        would answer for a namesake. The column names are aliased to the shape `_is_classified`
        and `_decode` already expect, so the rest of this facade does not fork per platform.
        """
        from taktik.core.database.local.service import get_local_database

        placeholders = ",".join("?" * len(usernames))
        rows = get_local_database().profiles.query(
            f"""
            SELECT username,
                   ai_niche          AS niche_category,
                   ai_specific_niche AS niche,
                   ai_profession     AS profession,
                   ai_profession_tags AS profession_tags,
                   location_city     AS cities,
                   analysis_json
            FROM profile_qualification
            WHERE platform = 'tiktok'
              AND lower(username) IN ({placeholders})
            """,
            tuple(name.lower() for name in usernames),
        )
        return [dict(row) for row in (rows or [])]

    @staticmethod
    def load_many(
        usernames: List[str], platform: str = "instagram"
    ) -> Dict[str, Dict[str, Any]]:
        """Stored qualifications for `usernames`, keyed by lowercased username.

        Only profiles carrying a real classification are returned; a username absent from the
        result means "classify it". Never raises.
        """
        if not usernames or platform not in SUPPORTED_PLATFORMS:
            return {}
        try:
            if platform == "tiktok":
                rows = ProfileQualification._tiktok_rows(usernames)
            else:
                rows = ProfileQualification._db().get_profiles_by_usernames(usernames) or []
        except Exception as exc:  # noqa: BLE001 — a lookup failure must never cost a run
            logger.debug(f"Qualification lookup failed for {len(usernames)} username(s): {exc}")
            return {}

        found: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            row = dict(row)
            if not ProfileQualification._is_classified(row):
                continue
            key = str(row.get("username", "")).lower()
            if key:
                found[key] = ProfileQualification._decode(row)
        return found

    @staticmethod
    def load(username: str, platform: str = "instagram") -> Optional[Dict[str, Any]]:
        """This profile's stored qualification, or None when it must be classified."""
        if not username:
            return None
        return ProfileQualification.load_many([username], platform).get(username.lower())


__all__ = ["ProfileQualification", "SUPPORTED_PLATFORMS"]
