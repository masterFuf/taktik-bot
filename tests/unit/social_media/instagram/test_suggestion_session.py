"""Automation session wrapped around a suggestions pass.

What these tests protect: a follow recorded without a session id does exist in the
interactions table, but it belongs to no session, so it surfaces neither in the
l'historique, ni dans l'instantane ``stats_*``, ni dans « on a gagne tant d'abonnes
history nor in the figures. That was the case everywhere the full automation object
is absent.
"""

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.common import (
    suggestion_session as module,
)


class _FakeDb:
    def __init__(self, session_id=42):
        self._session_id = session_id
        self.created = []
        self.finalized = []

    def create_session(self, **kwargs):
        self.created.append(kwargs)
        return self._session_id

    def finalize_session(self, session_id, status, **kwargs):
        self.finalized.append({"session_id": session_id, "status": status, **kwargs})
        return True


@pytest.fixture
def db(monkeypatch):
    fake = _FakeDb()
    monkeypatch.setattr("taktik.core.database.local.service.get_local_database",
                        lambda: fake)
    return fake


def test_a_session_is_opened_for_the_pass(db):
    session_id = module.open_suggestion_session(7, source="notifications")

    assert session_id == 42
    assert db.created[0]["account_id"] == 7
    assert db.created[0]["target_type"] == module.SUGGESTION_TARGET_TYPE
    assert db.created[0]["target"] == "notifications"


def test_without_an_account_no_session_is_opened(db):
    """Creating the session under the default id would attribute the work to someone
    else, which is worse than having no session at all."""
    assert module.open_suggestion_session(None, source="notifications") is None
    assert db.created == []


def test_the_pass_closes_its_session_with_a_stats_snapshot(db):
    with module.suggestion_session(7, source="notifications") as session_id:
        assert session_id == 42

    # Finalisation rather than a plain update: only it aggregates the session
    # interactions into the statistics columns. Without it the session would stay
    # active with zeroed counters while the follows sit in the database.
    assert db.finalized[0]["session_id"] == 42
    assert db.finalized[0]["status"] == "COMPLETED"
    assert "duration_seconds" in db.finalized[0]


def test_an_interrupted_pass_is_closed_in_error_and_not_left_active(db):
    """A session that never ends skews the averages as much as a missing one."""
    with pytest.raises(RuntimeError):
        with module.suggestion_session(7, source="notifications"):
            raise RuntimeError("device lost")

    assert db.finalized[0]["status"] == "ERROR"
    assert "device lost" in db.finalized[0]["error_message"]


def test_a_pass_without_session_closes_nothing(db):
    with module.suggestion_session(None, source="notifications") as session_id:
        assert session_id is None

    assert db.finalized == []


def test_a_database_failure_never_breaks_the_pass(monkeypatch):
    """Metrics matter, but not to the point of preventing the work from happening."""
    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr("taktik.core.database.local.service.get_local_database", _boom)

    with module.suggestion_session(7, source="notifications") as session_id:
        assert session_id is None  # carry on without a session rather than fail


def test_the_session_manager_carries_the_id_the_recorder_reads():
    """The session id is looked up on the manager, but the attribute existed nowhere,
    so every run outside the full automation object wrote its interactions with no
    session id."""
    from taktik.core.social_media.instagram.workflows.management.session import SessionManager

    manager = SessionManager({"session_settings": {}})

    assert hasattr(manager, "session_id")
    assert manager.session_id is None


def test_the_built_pipeline_reports_the_session_to_the_recorder():
    from unittest.mock import MagicMock

    from taktik.core.social_media.instagram.workflows.management.notifications import (
        build_notifications_profile_pipeline,
    )

    pipeline = build_notifications_profile_pipeline(
        MagicMock(), account_id=7, session_id=99,
    )

    assert pipeline.business._get_session_id() == 99
