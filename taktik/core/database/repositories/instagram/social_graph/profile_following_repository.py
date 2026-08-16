"""Who follows whom, as discovered during deep qualify — and what the AI made of them.

Owns `profile_following`: the edges found when a profile's following list is read, plus the
niche/gender classification later inferred for those accounts.

Distinct from `social_graph_repository`, which owns the bot account's OWN following/followers
sync. This one is about OTHER people's edges, used to build seed lists ("everyone we know of
who follows @source").

The enriched reads go through `profile_ai_read_model`, which inspects the schema before
building its SELECT: the AI columns live in `profile_ai_enrichments` on a current base, but a
standalone base may predate that table. Asking SQLite what exists beats assuming.
"""

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from ..._base.base_repository import BaseRepository


def profile_ai_read_model(conn: sqlite3.Connection, profile_alias: str) -> Dict[str, str]:
    """SQL fragments for reading a profile's AI fields, adapted to what the base has.

    Returns the JOIN and the four column expressions. On a base without
    `profile_ai_enrichments`, the AI fields resolve to NULL rather than failing the query —
    a standalone bot reads what it has instead of erroring.
    """
    # PRAGMA table_info yields (cid, name, type, notnull, default, pk). Read the name by
    # POSITION rather than by key: the repositories set `row_factory = sqlite3.Row`, but this
    # function is also reachable with a plain connection, where a row is a bare tuple.
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(instagram_profiles)").fetchall()
    }

    def column(name: str) -> str:
        return f"{profile_alias}.{name}" if name in columns else "NULL"

    factual = {
        "niche": "NULL",
        "sub_niche": "NULL",
        "profession": "NULL",
        "city": column("location_city"),
    }

    has_enrichment = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = 'profile_ai_enrichments'"
    ).fetchone() is not None

    if not has_enrichment:
        return {"join": "", **factual}

    return {
        "join": f"""
                LEFT JOIN profile_ai_enrichments pae
                    ON pae.enrichment_id = (
                        SELECT latest_pae.enrichment_id
                        FROM profile_ai_enrichments latest_pae
                        WHERE latest_pae.platform = 'instagram'
                        AND latest_pae.profile_id = {profile_alias}.profile_id
                        ORDER BY datetime(latest_pae.updated_at) DESC, latest_pae.enrichment_id DESC
                        LIMIT 1
                    )
        """,
        "niche": "pae.ai_niche",
        "sub_niche": "pae.ai_specific_niche",
        "profession": "pae.ai_profession",
        "city": f"COALESCE(pae.location_city, {factual['city']})",
    }


class ProfileFollowingRepository(BaseRepository):
    """Following edges discovered on other profiles, and their classification."""

    def save_edges(
        self,
        profile_username: str,
        following_usernames: List[str],
        session_id: Optional[str] = None,
        profile_id: Optional[int] = None,
    ) -> int:
        """Record who `profile_username` follows. Returns the number of NEW rows.

        `INSERT OR IGNORE`, so re-reading the same profile never raises on the unique
        constraint — it simply inserts nothing.

        The count comes from `cursor.rowcount`, NOT from `SELECT changes()`. After an
        `executemany`, `changes()` reports the last statement only: inserting 200 edges
        returned 1. The caller logs this number, so the trace claimed one new edge for a
        list of two hundred.
        """
        if not profile_username or not following_usernames:
            return 0
        try:
            if profile_id is None:
                row = self.query_one(
                    "SELECT profile_id FROM instagram_profiles WHERE username = ?",
                    (profile_username,),
                )
                if row:
                    profile_id = row[0]

            clean = [u for u in following_usernames if u]
            if not clean:
                return 0

            # One query to resolve every known following account, rather than one per name.
            placeholders = ",".join("?" * len(clean))
            id_rows = self.query(
                f"SELECT username, profile_id FROM instagram_profiles WHERE username IN ({placeholders})",
                tuple(clean),
            )
            following_id_map = {r[0]: r[1] for r in id_rows}

            cursor = self.conn.cursor()
            cursor.executemany(
                """
                INSERT OR IGNORE INTO profile_following
                    (profile_username, profile_id, following_username, following_id, session_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (profile_username, profile_id, u, following_id_map.get(u), session_id)
                    for u in clean
                ],
            )
            inserted = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
            self.conn.commit()
            return inserted
        except Exception as exc:
            logger.debug(f"save_edges failed for @{profile_username}: {exc}")
            return 0

    def save_classifications(self, classifications: Dict[str, Dict[str, str]]) -> int:
        """Persist AI-inferred niche/gender for following accounts. Returns rows updated.

        Only rows with `classified_at IS NULL` are touched: a classification is written
        once, so re-running the batch never overwrites an earlier verdict.
        """
        if not classifications:
            return 0
        updated = 0
        try:
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            cursor = self.conn.cursor()
            for username, data in classifications.items():
                cursor.execute(
                    """
                    UPDATE profile_following
                    SET niche_category = ?, niche = ?, gender = ?, classified_at = ?
                    WHERE following_username = ? AND classified_at IS NULL
                    """,
                    (
                        data.get("niche_category") or "other",
                        data.get("niche") or "Other",
                        data.get("gender") or "unknown",
                        now,
                        username,
                    ),
                )
                updated += cursor.rowcount if cursor.rowcount > 0 else 0
            self.conn.commit()
        except Exception as exc:
            logger.debug(f"save_classifications failed: {exc}")
        return updated

    def unclassified_usernames(self, limit: int = 200) -> List[str]:
        """Following accounts still awaiting a classification, newest discovery first."""
        try:
            rows = self.query(
                """
                SELECT DISTINCT following_username
                FROM profile_following
                WHERE classified_at IS NULL
                ORDER BY discovered_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [r[0] for r in rows]
        except Exception as exc:
            logger.debug(f"unclassified_usernames failed: {exc}")
            return []

    def profiles_following(self, following_username: str,
                           limit: int = 500) -> List[Dict[str, Any]]:
        """Everyone we know of who follows `following_username` — the seed-list read."""
        try:
            ai = profile_ai_read_model(self.conn, "p")
            rows = self.query(
                f"""
                SELECT
                    pf.profile_username,
                    pf.profile_id,
                    pf.discovered_at,
                    {ai["niche"]} AS niche_category,
                    {ai["sub_niche"]} AS niche,
                    {ai["city"]} AS cities,
                    {ai["profession"]} AS profession
                FROM profile_following pf
                LEFT JOIN instagram_profiles p
                    ON p.profile_id = pf.profile_id
                {ai["join"]}
                WHERE pf.following_username = ?
                ORDER BY pf.discovered_at DESC
                LIMIT ?
                """,
                (following_username, limit),
            )
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.debug(f"profiles_following failed for @{following_username}: {exc}")
            return []

    def following_of(self, profile_username: str) -> List[Dict[str, Any]]:
        """The stored following list of `profile_username`, enriched where known.

        Mirror of `profiles_following`, read from the other end of the edge.
        """
        try:
            ai = profile_ai_read_model(self.conn, "p")
            rows = self.query(
                f"""
                SELECT
                    pf.following_username,
                    pf.following_id,
                    pf.discovered_at,
                    {ai["niche"]} AS niche_category,
                    {ai["sub_niche"]} AS niche,
                    {ai["city"]} AS cities,
                    {ai["profession"]} AS profession
                FROM profile_following pf
                LEFT JOIN instagram_profiles p
                    ON p.profile_id = pf.following_id
                {ai["join"]}
                WHERE pf.profile_username = ?
                ORDER BY pf.discovered_at ASC
                """,
                (profile_username,),
            )
            return [dict(r) for r in rows]
        except Exception as exc:
            logger.debug(f"following_of failed for @{profile_username}: {exc}")
            return []


__all__ = ["ProfileFollowingRepository", "profile_ai_read_model"]
