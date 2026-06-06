"""Unit tests for the unified `interactions` table (Vague B Phase C)."""

from taktik.core.database.repositories.instagram.interaction import InteractionRepository
from taktik.core.database.local.migration_steps.interactions import (
    run_interactions_unification_migrations,
)


def test_record_writes_directly_into_unified_table(conn):
    repo = InteractionRepository(conn)
    conn.execute("INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (5, 'bot5', 1)")
    conn.execute("INSERT INTO instagram_profiles (profile_id, username) VALUES (50, 'target50')")
    conn.commit()

    repo.record(account_id=5, profile_id=50, interaction_type="like", success=True, content="ok")

    row = conn.execute(
        """SELECT platform, account_id, profile_id, interaction_type, success, content, legacy_id, sync_id
           FROM interactions WHERE account_id = 5 AND profile_id = 50""",
    ).fetchone()
    assert row["platform"] == "instagram"
    assert row["interaction_type"] == "LIKE"
    assert row["success"] == 1
    assert row["content"] == "ok"
    assert row["legacy_id"] is None      # direct write, no legacy row
    assert row["sync_id"] is not None    # generated for Turso cross-device dedup

    # No duplicate on a single record.
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM interactions WHERE account_id = 5 AND profile_id = 50",
    ).fetchone()
    assert count["c"] == 1


def test_phase_c_migrate_then_drop_is_idempotent(conn):
    """A legacy interaction_history row is migrated into interactions and the
    legacy tables are then dropped, idempotently (Phase C)."""
    conn.execute("INSERT INTO instagram_accounts (account_id, username, is_bot) VALUES (6, 'bot6', 1)")
    conn.execute("INSERT INTO instagram_profiles (profile_id, username) VALUES (60, 'ig60')")
    # Recreate a legacy table (dropped by the migration) to simulate an old base.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interaction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, account_id INTEGER NOT NULL,
            profile_id INTEGER NOT NULL, interaction_type TEXT NOT NULL,
            interaction_time TEXT DEFAULT (datetime('now')), success INTEGER DEFAULT 1, content TEXT,
            sync_id TEXT)
    """)
    conn.execute(
        "INSERT INTO interaction_history (account_id, profile_id, interaction_type, success, sync_id) "
        "VALUES (6, 60, 'FOLLOW', 1, 'legacy-sync-1')",
    )
    conn.commit()

    run_interactions_unification_migrations(conn.cursor())
    run_interactions_unification_migrations(conn.cursor())  # idempotent

    row = conn.execute(
        "SELECT COUNT(*) AS c, MAX(sync_id) AS s FROM interactions "
        "WHERE platform = 'instagram' AND account_id = 6 AND profile_id = 60",
    ).fetchone()
    assert row["c"] == 1
    assert row["s"] == "legacy-sync-1"  # legacy sync_id carried
    # legacy table dropped by the Phase C migration
    dropped = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='interaction_history'",
    ).fetchone()
    assert dropped is None
