"""A cold DM run is one session, like an automation run.

The run wrote its DMs to `sent_dms` and no session at all: its AI spend, which the desktop totals
from `ai_spend`, had no row to land in, and the AI COST tile never saw it. The launcher now opens a
`sessions_unified` row (workflow `cold_dm`), hands its id to the host (`session_start` on the
bridge) and closes it with its status, duration and stop reason. These tests run the real launcher
on a throwaway base; the workflow itself is a stand-in.
"""
import pytest

from taktik.core.social_media.instagram.workflows.cold_dm.agent_handler import (
    ColdDmRuntime,
    run_instagram_cold_dm,
)


def _query(db, sql, params=()):
    return [dict(row) for row in db._get_connection().execute(sql, params).fetchall()]


@pytest.fixture
def base(db, monkeypatch):
    monkeypatch.setattr("taktik.core.database.local.service.get_local_database", lambda: db)
    return db


@pytest.fixture
def phone_account(base):
    account_id, _created = base.get_or_create_account(username="phone_account")
    return account_id


def _sessions(db):
    return _query(
        db,
        "SELECT legacy_session_id, account_id, workflow_type, target_type, target, status, end_time, "
        "duration_seconds, error_message, stop_reason_code, config_used "
        "FROM sessions_unified WHERE platform = 'instagram' ORDER BY id",
    )


def _workflow(result=None, raises=None, seen=None):
    class _Workflow:
        def __init__(self, *a, **k):
            pass

        def run(self, recipients, messages, delay_min, delay_max, max_dms, account_id, session_id, *a, **k):
            if seen is not None:
                seen.update(account_id=account_id, session_id=session_id)
            if raises is not None:
                raise raises
            return result

    return _Workflow


def _run(payload, workflow, started=None):
    return run_instagram_cold_dm(
        {"deviceId": "phone-1", "recipients": ["ana", "@bob", "cid"], "messages": ["hi"], **payload},
        runtime=ColdDmRuntime(device=None, device_manager=None, keyboard=None),
        workflow_factory=workflow,
        on_session_start=(started.append if started is not None else None),
    )


def test_a_run_is_one_completed_session_under_the_account_seen_on_the_phone(base, phone_account):
    started, seen = [], {}
    result = _run({"sessionAccountId": phone_account, "openrouterApiKey": "sk-or-v1-secret"},
                  _workflow({"success": True, "dms_sent": 2, "dms_success": 2}, seen=seen), started)

    assert result["dms_sent"] == 2
    rows = _sessions(base)
    assert len(rows) == 1
    row = rows[0]
    assert started == [row["legacy_session_id"]]
    assert row["account_id"] == phone_account
    assert row["workflow_type"] == "cold_dm"
    assert row["target_type"] == "DM"
    assert row["target"] == "@ana (+2)"
    assert row["status"] == "COMPLETED"
    assert row["end_time"] is not None
    assert row["duration_seconds"] is not None
    assert row["stop_reason_code"] == "completed"
    assert "sk-or-v1-secret" not in row["config_used"]
    # The duplicate check of sent_dms keeps its own account and session keys.
    assert seen == {"account_id": 1, "session_id": "phone-1"}


def test_without_a_known_account_no_session_is_opened(base):
    started = []
    _run({}, _workflow({"success": True, "dms_sent": 1}), started)

    assert _sessions(base) == []
    assert started == []


def test_an_explicit_account_of_the_payload_is_the_session_account(base, phone_account):
    _run({"accountId": phone_account}, _workflow({"success": True, "dms_sent": 0}))

    assert [row["account_id"] for row in _sessions(base)] == [phone_account]


def test_a_refused_run_closes_its_session_in_error(base, phone_account):
    _run({"sessionAccountId": phone_account}, _workflow({"success": False, "error": "No recipients provided"}))

    row = _sessions(base)[0]
    assert row["status"] == "ERROR"
    assert row["error_message"] == "No recipients provided"
    assert row["end_time"] is not None


def test_a_crash_closes_the_session_in_error_and_still_raises(base, phone_account):
    with pytest.raises(RuntimeError):
        _run({"sessionAccountId": phone_account}, _workflow(raises=RuntimeError("screen lost")))

    row = _sessions(base)[0]
    assert row["status"] == "ERROR"
    assert row["stop_reason_code"] == "crashed"
    assert "screen lost" in row["error_message"]


def test_a_stopped_run_is_filed_as_a_manual_stop(base, phone_account):
    with pytest.raises(KeyboardInterrupt):
        _run({"sessionAccountId": phone_account}, _workflow(raises=KeyboardInterrupt()))

    row = _sessions(base)[0]
    assert row["status"] == "STOPPED"
    assert row["stop_reason_code"] == "manual_stop"


def test_the_session_counts_in_the_daily_sessions_of_its_account(base, phone_account):
    _run({"sessionAccountId": phone_account}, _workflow({"success": True, "dms_sent": 1}))

    rows = _query(
        base,
        "SELECT total_sessions, completed_sessions FROM daily_stats_unified "
        "WHERE platform = 'instagram' AND account_id = ?",
        (phone_account,),
    )
    assert [(r["total_sessions"], r["completed_sessions"]) for r in rows] == [(1, 1)]


def test_create_session_stores_the_workflow_type_it_is_given(db):
    account_id, _created = db.get_or_create_account(username="someone")
    session_id = db.create_session(account_id=account_id, session_name="x", target_type="DM", target="@a",
                                   workflow_type="cold_dm")

    row = _query(
        db,
        "SELECT workflow_type FROM sessions_unified WHERE platform = 'instagram' AND legacy_session_id = ?",
        (session_id,),
    )[0]
    assert row["workflow_type"] == "cold_dm"
