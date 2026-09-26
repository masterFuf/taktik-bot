"""The end of a TikTok scraping row: stored in UTC, with a status of the contract.

The start of a `scraping_sessions` row is SQLite's `datetime('now')`, UTC. The end was written as
`datetime.now().isoformat()`, local time with a `T`: every duration read from the two columns was
off by the machine's offset. A stop by the operator was filed `STOPPED`, which the contract
(`scraping_session_repository.py`) does not know: it says `CANCELLED`.
"""

import sqlite3

import pytest

import taktik.core.database.tiktok_scraping as scraping_store
from taktik.core.database.local.schemas.scraping import scraping_sessions_ddl


@pytest.fixture
def conn(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(scraping_sessions_ddl())
    monkeypatch.setattr(scraping_store, "get_repository", lambda repo_class: repo_class(connection))
    yield connection
    connection.close()


def _row(conn, scraping_id):
    return conn.execute("SELECT * FROM scraping_sessions WHERE scraping_id = ?", (scraping_id,)).fetchone()


def test_the_end_is_stored_in_utc_like_the_start(conn):
    scraping_id = scraping_store.open_scraping_session("HASHTAG", "#food")

    scraping_store.close_scraping_session(scraping_id, 3, "COMPLETED", 12)

    row = _row(conn, scraping_id)
    assert row["status"] == "COMPLETED"
    assert len(row["end_time"]) == 19 and "T" not in row["end_time"], row["end_time"]
    gap = conn.execute(
        "SELECT ABS(julianday(end_time) - julianday(start_time)) * 86400 FROM scraping_sessions WHERE scraping_id = ?",
        (scraping_id,),
    ).fetchone()[0]
    assert gap < 5, gap


def test_a_stop_by_the_operator_is_cancelled(conn):
    scraping_id = scraping_store.open_scraping_session("HASHTAG", "#food")

    scraping_store.close_scraping_session(scraping_id, 1, "CANCELLED", 4)

    assert _row(conn, scraping_id)["status"] == "CANCELLED"


def test_a_status_outside_the_contract_is_refused(conn):
    scraping_id = scraping_store.open_scraping_session("HASHTAG", "#food")

    with pytest.raises(ValueError):
        scraping_store.close_scraping_session(scraping_id, 1, "STOPPED", 4)

    assert _row(conn, scraping_id)["status"] == "RUNNING"
