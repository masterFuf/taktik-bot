"""Unit tests for the unified `daily_stats_unified` table (Vague B Phase C)."""

from datetime import datetime

from taktik.core.database.repositories.instagram.stats import StatsRepository
from taktik.core.database.local.migration_steps.daily_stats import (
    run_daily_stats_unification_migrations,
)


def test_increment_writes_directly_into_unified_table(conn):
    repo = StatsRepository(conn)
    conn.execute("INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (5, 'bot5', 1)")
    conn.commit()

    repo.increment_interaction(5, "LIKE")
    repo.increment_interaction(5, "FOLLOW")

    today = datetime.now().strftime('%Y-%m-%d')
    row = conn.execute(
        """SELECT platform, total_likes, total_follows
           FROM daily_stats_unified WHERE account_id = 5 AND date = ?""",
        (today,),
    ).fetchone()
    assert row is not None
    assert row["platform"] == "instagram"
    assert row["total_likes"] == 1
    assert row["total_follows"] == 1

    # Re-running the backfill must not duplicate the mirrored row.
    run_daily_stats_unification_migrations(conn.cursor())
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM daily_stats_unified WHERE account_id = 5 AND date = ?",
        (today,),
    ).fetchone()
    assert count["c"] == 1


def test_phase_c_migrate_then_drop_is_idempotent(conn):
    """Legacy daily_stats rows are migrated into daily_stats_unified and the legacy
    tables are then dropped, idempotently (Phase C)."""
    conn.execute("INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (6, 'bot6', 1)")
    # Recreate a legacy table (dropped by the migration) to simulate an old base.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, date TEXT NOT NULL,
            total_likes INTEGER DEFAULT 0, total_follows INTEGER DEFAULT 0, total_unfollows INTEGER DEFAULT 0,
            total_comments INTEGER DEFAULT 0, total_story_views INTEGER DEFAULT 0, total_story_likes INTEGER DEFAULT 0,
            total_profile_visits INTEGER DEFAULT 0, total_sessions INTEGER DEFAULT 0, completed_sessions INTEGER DEFAULT 0,
            failed_sessions INTEGER DEFAULT 0, total_duration_seconds INTEGER DEFAULT 0, synced_to_api INTEGER DEFAULT 0,
            synced_at TEXT, created_at TEXT, updated_at TEXT, UNIQUE(account_id, date))
    """)
    conn.execute(
        "INSERT INTO daily_stats (account_id, date, total_likes, total_story_views) VALUES (6, '2026-01-01', 3, 9)",
    )
    conn.commit()

    run_daily_stats_unification_migrations(conn.cursor())
    run_daily_stats_unification_migrations(conn.cursor())  # idempotent

    ig = conn.execute(
        "SELECT total_likes, total_story_views FROM daily_stats_unified "
        "WHERE platform = 'instagram' AND account_id = 6 AND date = '2026-01-01'",
    ).fetchall()
    assert len(ig) == 1
    assert ig[0]["total_likes"] == 3
    assert ig[0]["total_story_views"] == 9
    # legacy table dropped by the Phase C migration
    dropped = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_stats'",
    ).fetchone()
    assert dropped is None
