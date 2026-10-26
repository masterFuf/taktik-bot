"""A run whose base does not open says so: its code names the database, not the licence.

The Instagram automation sent `LICENSE_SETUP_FAILED` when `configure_db_service` failed, a name left
from the time a licence check sat at that step: the app said « Erreur de verification de licence »
for a base that would not open.
"""
from __future__ import annotations

import bridges.instagram.automation.session as session
from bridges.common.ipc import IPC


def test_a_base_that_does_not_open_is_reported_as_a_database_failure(monkeypatch):
    sent = []
    monkeypatch.setattr(session, "send_status", lambda *a, **k: None)
    # The line goes out through `send_run_error`, by the IPC class (patched there, not on an instance).
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **data: sent.append(data.get("error_code"))
                        if msg_type == "error" else None)

    def refuse():
        raise OSError("unable to open database file")

    monkeypatch.setattr("taktik.core.database.configure_db_service", refuse)
    runtime = session.InstagramDesktopRuntime(device_id="emulator-5554", network_reset={})

    assert runtime.setup_database() is False
    assert sent == ["DATABASE_SETUP_FAILED"]
