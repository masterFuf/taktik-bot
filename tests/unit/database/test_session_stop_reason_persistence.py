"""Why a run ended must survive the process that ran it.

The motive travelled in the `session_stop` event and died there: `sessions_unified` kept a
three-valued status and an `error_message` the bot never filled. A run that ended on
`navigation_lost` and one that hit its duration cap were indistinguishable the next day.
"""

from taktik.core.social_media.instagram.workflows.management.session import stop_reasons


def _create_session(db) -> int:
    account_id, _ = db.get_or_create_account("taktik_test")
    session_id = db.create_session(account_id, "test run", "TARGET", "@target")
    assert session_id
    return session_id


def _row(db, session_id: int):
    return db.sessions.query_one(
        "SELECT status, stop_reason_code, stop_reason_params, error_message "
        "FROM sessions_unified WHERE platform = 'instagram' AND legacy_session_id = ?",
        (session_id,),
    )


def test_the_column_exists_after_migrations(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions_unified)").fetchall()}
    assert "stop_reason_code" in columns
    assert "stop_reason_params" in columns


def test_an_ok_reason_is_written_with_its_params(db):
    session_id = _create_session(db)

    assert db.finalize_session(
        session_id, "COMPLETED",
        duration_seconds=120,
        stop_reason=stop_reasons.duration_cap(45),
    )

    row = _row(db, session_id)
    assert row["status"] == "COMPLETED"
    assert row["stop_reason_code"] == "duration_cap"
    assert '"minutes": 45' in row["stop_reason_params"] or '"minutes":45' in row["stop_reason_params"]
    # A legitimate end is not an error, so error_message stays empty.
    assert not row["error_message"]


def test_a_failed_reason_also_fills_the_error_message(db):
    """`error_message` is what every existing reader shows; a failed run must not read as blank."""
    session_id = _create_session(db)

    assert db.finalize_session(session_id, "INTERRUPTED", stop_reason=stop_reasons.navigation_lost())

    row = _row(db, session_id)
    assert row["stop_reason_code"] == "navigation_lost"
    assert row["error_message"] == "navigation_lost"


def test_a_crash_is_persisted_as_such(db):
    session_id = _create_session(db)

    assert db.finalize_session(session_id, "ERROR", stop_reason=stop_reasons.crashed(RuntimeError("boom")))

    row = _row(db, session_id)
    assert row["status"] == "ERROR"
    assert row["stop_reason_code"] == "crashed"
    assert "boom" in row["error_message"]


def test_no_reason_leaves_the_columns_alone(db):
    """Callers that never pass a motive keep working exactly as before."""
    session_id = _create_session(db)

    assert db.finalize_session(session_id, "COMPLETED", duration_seconds=10)

    row = _row(db, session_id)
    assert row["stop_reason_code"] is None
    assert row["stop_reason_params"] is None
