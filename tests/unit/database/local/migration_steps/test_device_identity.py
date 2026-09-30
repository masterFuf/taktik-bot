"""Device identity: a stable per-PC id, stamped on every new interaction row.

The database syncs across several PCs (Turso) but rows carried no trace of which
device created them — sync maintenance had to guess ownership from a timestamp
heuristic. Every interaction INSERT now stamps origin_device_id via a scalar
subquery on the single-row device_identity table (created idempotently by both
the bot and Electron migrations).
"""

from taktik.core.database.repositories.instagram.interaction.interaction_repository import InteractionRepository


def test_device_identity_created_once_and_stable(conn):
    row = conn.execute("SELECT device_id FROM device_identity WHERE id = 1").fetchone()
    assert row is not None and len(row["device_id"]) == 16

    # Re-running the migration must not regenerate the id.
    from taktik.core.database.local.migration_steps.device import run_device_identity_migrations

    run_device_identity_migrations(conn.cursor())
    again = conn.execute("SELECT device_id FROM device_identity WHERE id = 1").fetchone()
    assert again["device_id"] == row["device_id"]


def test_interaction_rows_are_stamped_with_the_device_id(conn):
    conn.execute(
        "INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES ('instagram', 1, 'bot', 1)"
    )
    repo = InteractionRepository(conn)
    row_id = repo.record(account_id=1, profile_id=10, interaction_type='LIKE')

    stored = conn.execute(
        "SELECT origin_device_id FROM interactions WHERE id = ?", (row_id,)
    ).fetchone()
    device = conn.execute("SELECT device_id FROM device_identity WHERE id = 1").fetchone()
    assert stored["origin_device_id"] == device["device_id"]
