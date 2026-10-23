"""Who follows whom, as discovered during deep qualify — and what the AI made of them.

Owns `profile_following`: the edges found when a profile's following list is read, plus the
niche/gender classification later inferred for those accounts.

Distinct from `social_graph_repository`, which owns the bot account's OWN following/followers
sync. This one is about OTHER people's edges: it writes and classifies them, and reads
the pending ones.

No method here swallows a refusal of the base: a write rolls back and raises, a read raises.
A 0 or an empty list would read as a measure ("nothing new", "nothing pending"), and only the
caller knows whether its run goes on and what to say.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..._base.base_repository import BaseRepository


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

        A refused write raises, after a rollback: returning 0 would read as "every edge
        already known", and the first edges of a refused list would wait in the open
        transaction for the next commit of another repository on the same connection.
        """
        if not profile_username or not following_usernames:
            return 0
        clean = [u for u in following_usernames if u]
        if not clean:
            return 0
        try:
            if profile_id is None:
                row = self.query_one(
                    "SELECT profile_id FROM instagram_profiles WHERE username = ?",
                    (profile_username,),
                )
                if row:
                    profile_id = row[0]

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
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return inserted

    def save_classifications(self, classifications: Dict[str, Dict[str, str]]) -> int:
        """Persist AI-inferred niche/gender for following accounts. Returns rows updated.

        Only rows with `classified_at IS NULL` are touched: a classification is written
        once, so re-running the batch never overwrites an earlier verdict.

        A refused write raises, after a rollback: returning 0 would read as "already
        classified", and the verdicts were paid for. The workflow says the loss.
        """
        if not classifications:
            return 0
        updated = 0
        try:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
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
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return updated

    def unclassified_usernames(self, limit: int = 200) -> List[str]:
        """Following accounts still awaiting a classification, newest discovery first.

        A refused read raises: an empty list would read as "nothing left to classify".
        """
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


__all__ = ["ProfileFollowingRepository"]
