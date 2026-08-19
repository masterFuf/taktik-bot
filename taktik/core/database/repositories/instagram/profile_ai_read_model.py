"""How a profile's AI fields are read — one implementation, for every base shape.

Two shapes exist in the wild and both are legitimate:

  - **desktop**: the front unified every qualification overlay into `profile_qualification`
    (UNIQUE on platform+username) and left `profile_ai_enrichments` behind as a read-only
    compat VIEW over it;
  - **standalone**: the open-source bot never runs that unification, so
    `profile_ai_enrichments` is a real TABLE and `profile_qualification` does not exist.

This module used to be copy-pasted in `profile/profile_repository.py` and in
`social_graph/profile_following_repository.py`, and both copies asked sqlite_master for a
**TABLE** named `profile_ai_enrichments`. On a desktop base that name is a **VIEW**, so the
answer was no and every AI column resolved to a literal `NULL` — silently, no error, no
warning: 40k stored qualifications read back as "never classified", the interaction hook's
reuse gate never fired once, and every profile was re-sent to the vision model on every pass.
**Ask what exists, never what type it is.**

Two data facts decide the join, and both were verified against a production base before
being relied on:

  - the join key is `(platform, username)`, the table's own UNIQUE constraint — NOT
    `profile_id`. 636 profile_ids carry two qualification rows for two unrelated usernames
    (`cheerleader_jaslyn` and `brasserie_la_vallee` share one id), so a profile_id join both
    multiplies rows and serves one profile's niche for another's.
  - `has_ai = 1` alone does NOT mean "classified": 19 039 rows of 40 353 carry the flag with
    every AI column still NULL. The flag gates the join; whether a usable classification came
    back is the caller's check (see `taktik/core/database/profile_qualification.py`).

Reading `profile_qualification` directly is also what keeps the join cheap: one row per
platform+username means no correlated "latest row" subquery. That subquery — unavoidable on
the standalone shape, where several enrichment rows may stack per profile — is what measured
>20s over 154k rows when a bulk query went through the compat view.
"""

import sqlite3
from typing import Dict

PLATFORM = "instagram"


def _exists(conn: sqlite3.Connection, name: str) -> bool:
    """Whether `name` is queryable — table OR view.

    The distinction is a storage detail; both answer the same SELECT. Testing for
    `type='table'` is what silently disabled the whole read model on a desktop base.
    """
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = ? AND type IN ('table', 'view')",
        (name,),
    ).fetchone() is not None


def profile_ai_read_model(conn: sqlite3.Connection, profile_alias: str) -> Dict[str, str]:
    """SQL fragments for reading a profile's AI fields, adapted to what the base has.

    `profile_alias` is the alias of the `instagram_profiles` row in the caller's query.
    Returns the JOIN clause plus one expression per exposed field; on a base that carries
    neither store, the AI fields resolve to NULL rather than failing the query, so a
    standalone bot reads what it has instead of erroring.
    """
    # PRAGMA table_info yields (cid, name, type, notnull, default, pk). Read the name by
    # POSITION rather than by key: the repositories set `row_factory = sqlite3.Row`, but this
    # function is also reachable with a plain connection, where a row is a bare tuple.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(instagram_profiles)").fetchall()}
    city = f"{profile_alias}.location_city" if "location_city" in columns else "NULL"

    if _exists(conn, "profile_qualification"):
        return {
            "join": f"""
                LEFT JOIN profile_qualification pq
                    ON pq.platform = '{PLATFORM}'
                    AND pq.username = {profile_alias}.username
                    AND pq.has_ai = 1
            """,
            "niche": "pq.ai_niche",
            "sub_niche": "pq.ai_specific_niche",
            "profession": "pq.ai_profession",
            "profession_tags": "pq.ai_profession_tags",
            "city": f"COALESCE(pq.location_city, {city})",
            "analysis": "pq.analysis_json",
        }

    if _exists(conn, "profile_ai_enrichments"):
        # Standalone shape: enrichments stack per profile, so the latest one wins.
        return {
            "join": f"""
                LEFT JOIN profile_ai_enrichments pae
                    ON pae.enrichment_id = (
                        SELECT latest_pae.enrichment_id
                        FROM profile_ai_enrichments latest_pae
                        WHERE latest_pae.platform = '{PLATFORM}'
                        AND latest_pae.profile_id = {profile_alias}.profile_id
                        ORDER BY datetime(latest_pae.updated_at) DESC, latest_pae.enrichment_id DESC
                        LIMIT 1
                    )
            """,
            "niche": "pae.ai_niche",
            "sub_niche": "pae.ai_specific_niche",
            "profession": "pae.ai_profession",
            "profession_tags": "pae.ai_profession_tags",
            "city": f"COALESCE(pae.location_city, {city})",
            "analysis": "pae.analysis_json",
        }

    return {
        "join": "",
        "niche": "NULL",
        "sub_niche": "NULL",
        "profession": "NULL",
        "profession_tags": "NULL",
        "city": city,
        "analysis": "NULL",
    }


__all__ = ["profile_ai_read_model", "PLATFORM"]
