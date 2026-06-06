"""Unit tests for the unified `sessions_unified` table (Vague B Phase A)."""

from taktik.core.database.repositories.instagram.session import SessionRepository
from taktik.core.database.local.migration_steps.sessions import (
    run_sessions_unification_migrations,
)


def test_create_and_update_mirror_into_unified_table(conn):
    repo = SessionRepository(conn)
    conn.execute("INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (5, 'bot5', 1)")
    conn.commit()

    session_id = repo.create(5, "run-5", "USER", "target5", {"k": "v"})
    assert session_id is not None

    row = conn.execute(
        """SELECT platform, legacy_session_id, account_id, target_type, target, status
           FROM sessions_unified WHERE platform = 'instagram' AND legacy_session_id = ?""",
        (session_id,),
    ).fetchone()
    assert row is not None
    assert row["account_id"] == 5
    assert row["target_type"] == "USER"
    assert row["target"] == "target5"

    repo.update(session_id, status="COMPLETED", duration_seconds=42)
    row = conn.execute(
        "SELECT status, duration_seconds FROM sessions_unified "
        "WHERE platform = 'instagram' AND legacy_session_id = ?",
        (session_id,),
    ).fetchone()
    assert row["status"] == "COMPLETED"
    assert row["duration_seconds"] == 42

    # Re-running the backfill must not duplicate the mirrored row.
    run_sessions_unification_migrations(conn.cursor())
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM sessions_unified WHERE platform = 'instagram' AND legacy_session_id = ?",
        (session_id,),
    ).fetchone()
    assert count["c"] == 1


def test_backfill_both_platforms_is_idempotent(conn):
    conn.execute("INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (6, 'bot6', 1)")
    conn.execute("INSERT INTO tiktok_accounts (account_id, username, is_bot) VALUES (7, 'tt7', 1)")
    # Use base columns present in the bot-standalone legacy schemas (the front adds
    # stats_*/ai_* to sessions; the column-aware copy handles those on the real DB).
    conn.execute(
        """INSERT INTO sessions (session_id, account_id, session_name, target_type, target, status)
           VALUES (600, 6, 'ig-run', 'HASHTAG', '#x', 'COMPLETED')""",
    )
    conn.execute(
        """INSERT INTO tiktok_sessions (session_id, account_id, session_name, workflow_type, target, status, likes)
           VALUES (700, 7, 'tt-run', 'automation', '@y', 'COMPLETED', 22)""",
    )
    conn.commit()

    run_sessions_unification_migrations(conn.cursor())
    run_sessions_unification_migrations(conn.cursor())  # idempotent

    ig = conn.execute(
        "SELECT target_type, target FROM sessions_unified "
        "WHERE platform = 'instagram' AND legacy_session_id = 600",
    ).fetchall()
    tt = conn.execute(
        "SELECT workflow_type, likes FROM sessions_unified "
        "WHERE platform = 'tiktok' AND legacy_session_id = 700",
    ).fetchall()
    assert len(ig) == 1
    assert ig[0]["target_type"] == "HASHTAG"
    assert ig[0]["target"] == "#x"
    assert len(tt) == 1
    assert tt[0]["workflow_type"] == "automation"
    assert tt[0]["likes"] == 22
