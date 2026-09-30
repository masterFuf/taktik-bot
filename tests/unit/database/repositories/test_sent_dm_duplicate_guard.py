"""The duplicate guard, against a table that predates the `platform` column.

`ensure_table` used `CREATE TABLE IF NOT EXISTS` to declare a column added long after the table
existed, so on every real database the column was never created. Both queries then failed with
`no such column: platform`, and the service around them catches Exception and answers False —
"never messaged". Instagram cold DM had no duplicate protection at all, and the production table
holds 8 rows for months of runs.

The fixture is the LEGACY schema on purpose: a test starting from the current one would have
passed throughout.
"""

import sqlite3

import pytest

from taktik.core.database.repositories.messaging.sent_dm_repository import SentDMRepository

LEGACY_SCHEMA = """
    CREATE TABLE sent_dms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        recipient_username TEXT NOT NULL,
        message_hash TEXT,
        sent_at TEXT DEFAULT (datetime('now')),
        success INTEGER DEFAULT 1,
        error_message TEXT,
        session_id TEXT,
        UNIQUE(account_id, recipient_username)
    )
"""


@pytest.fixture
def legacy_repo():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(LEGACY_SCHEMA)
    connection.execute("INSERT INTO sent_dms (account_id, recipient_username) VALUES (1, 'deja')")
    connection.commit()
    return SentDMRepository(connection), connection


def _columns(connection):
    return [row[1] for row in connection.execute("PRAGMA table_info(sent_dms)")]


def test_a_known_recipient_is_recognised_on_a_legacy_table(legacy_repo):
    """The whole bug in one line: this used to raise, be swallowed, and answer False."""
    repo, _ = legacy_repo
    assert repo.check_already_sent(1, "deja") is True


def test_the_platform_column_is_added_rather_than_declared(legacy_repo):
    repo, connection = legacy_repo
    assert "platform" not in _columns(connection)
    repo.check_already_sent(1, "deja")
    assert "platform" in _columns(connection)


def test_an_unknown_recipient_is_still_unknown(legacy_repo):
    repo, _ = legacy_repo
    assert repo.check_already_sent(1, "jamais-vu") is False


def test_a_recorded_dm_is_found_again(legacy_repo):
    repo, _ = legacy_repo
    repo.record(2, "nouveau", "coucou", True)
    assert repo.check_already_sent(2, "nouveau") is True


def test_the_same_handle_on_another_platform_is_not_the_same_recipient(legacy_repo):
    """Instagram and TikTok share handles. A guard that conflated them would skip real targets."""
    repo, _ = legacy_repo
    repo.record(1, "commun", "salut", True, platform="instagram")
    assert repo.check_already_sent(1, "commun", "instagram") is True
    assert repo.check_already_sent(1, "commun", "tiktok") is False


def test_ensure_table_is_idempotent(legacy_repo):
    repo, connection = legacy_repo
    repo.ensure_table()
    repo.ensure_table()
    assert _columns(connection).count("platform") == 1
