"""Unit tests for the unified `daily_stats_unified` table (Vague B Phase A)."""

from datetime import datetime

from taktik.core.database.repositories.instagram.stats import StatsRepository
from taktik.core.database.local.migration_steps.daily_stats import (
    run_daily_stats_unification_migrations,
)


def test_increment_mirrors_into_unified_table(conn):
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


def test_backfill_both_platforms_is_idempotent(conn):
    conn.execute("INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (6, 'bot6', 1)")
    conn.execute("INSERT INTO tiktok_accounts (account_id, username, is_bot) VALUES (7, 'tt7', 1)")
    # Legacy-only rows (not mirrored via repos) — only the backfill should pick them up.
    conn.execute(
        """INSERT INTO daily_stats (account_id, date, total_likes, total_story_views)
           VALUES (6, '2026-01-01', 3, 9)""",
    )
    conn.execute(
        """INSERT INTO tiktok_daily_stats (account_id, date, total_likes, total_favorites, total_posts_watched)
           VALUES (7, '2026-01-01', 4, 5, 6)""",
    )
    conn.commit()

    run_daily_stats_unification_migrations(conn.cursor())
    run_daily_stats_unification_migrations(conn.cursor())  # idempotent

    ig = conn.execute(
        "SELECT total_likes, total_story_views FROM daily_stats_unified "
        "WHERE platform = 'instagram' AND account_id = 6 AND date = '2026-01-01'",
    ).fetchall()
    tt = conn.execute(
        "SELECT total_likes, total_favorites, total_posts_watched FROM daily_stats_unified "
        "WHERE platform = 'tiktok' AND account_id = 7 AND date = '2026-01-01'",
    ).fetchall()
    assert len(ig) == 1
    assert ig[0]["total_likes"] == 3
    assert ig[0]["total_story_views"] == 9
    assert len(tt) == 1
    assert tt[0]["total_likes"] == 4
    assert tt[0]["total_favorites"] == 5
    assert tt[0]["total_posts_watched"] == 6
