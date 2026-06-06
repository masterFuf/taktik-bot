"""Unit tests for the unified `interactions` table (Vague B Phase A)."""

from taktik.core.database.repositories.instagram.interaction import InteractionRepository
from taktik.core.database.local.migration_steps.interactions import (
    run_interactions_unification_migrations,
)


def test_interaction_dual_write_into_unified_table(conn):
    repo = InteractionRepository(conn)
    conn.execute("INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (5, 'bot5', 1)")
    conn.execute("INSERT INTO instagram_profiles (profile_id, username) VALUES (50, 'target50')")
    conn.commit()

    repo.record(account_id=5, profile_id=50, interaction_type="like", success=True, content="ok")

    row = conn.execute(
        """SELECT platform, account_id, profile_id, interaction_type, success, content
           FROM interactions WHERE account_id = 5 AND profile_id = 50""",
    ).fetchone()
    assert row["platform"] == "instagram"
    assert row["interaction_type"] == "LIKE"
    assert row["success"] == 1
    assert row["content"] == "ok"


def test_backfill_both_platforms_is_idempotent(conn):
    conn.execute("INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (6, 'bot6', 1)")
    conn.execute("INSERT INTO tiktok_accounts (account_id, username, is_bot) VALUES (7, 'tt7', 1)")
    conn.execute("INSERT INTO instagram_profiles (profile_id, username) VALUES (60, 'ig60')")
    conn.execute("INSERT INTO tiktok_profiles (profile_id, username) VALUES (70, 'tt70')")
    conn.commit()

    # Legacy-only rows (not mirrored via repos) — only the backfill should pick them up.
    conn.execute(
        """INSERT INTO interaction_history (account_id, profile_id, interaction_type, success, content)
           VALUES (6, 60, 'FOLLOW', 1, NULL)""",
    )
    conn.execute(
        """INSERT INTO tiktok_interaction_history (account_id, profile_id, interaction_type, success, content, video_id)
           VALUES (7, 70, 'LIKE', 1, NULL, 'vid1')""",
    )
    conn.commit()

    run_interactions_unification_migrations(conn.cursor())
    run_interactions_unification_migrations(conn.cursor())  # idempotent

    ig = conn.execute(
        "SELECT COUNT(*) AS c FROM interactions WHERE platform = 'instagram' AND account_id = 6 AND profile_id = 60",
    ).fetchone()
    tt = conn.execute(
        "SELECT platform, video_id, COUNT(*) AS c FROM interactions WHERE platform = 'tiktok' AND account_id = 7 AND profile_id = 70",
    ).fetchone()
    assert ig["c"] == 1
    assert tt["c"] == 1
    assert tt["video_id"] == "vid1"
