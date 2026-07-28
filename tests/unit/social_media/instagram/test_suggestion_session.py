"""Session d'automatisation autour d'une passe de suggestions.

Ce que ces tests protegent : un follow enregistre sans ``session_id`` existe bien dans
``interactions``, mais il n'appartient a aucune session — donc il ne remonte ni dans
l'historique, ni dans l'instantane ``stats_*``, ni dans « on a gagne tant d'abonnes
grace au bot ». C'etait le cas partout ou il n'y a pas d'``InstagramAutomation`` : le
Lab, et le bridge Notifications.
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
    """Creer la session sous l'id par defaut attribuerait le travail a quelqu'un
    d'autre — c'est pire que pas de session du tout."""
    assert module.open_suggestion_session(None, source="notifications") is None
    assert db.created == []


def test_the_pass_closes_its_session_with_a_stats_snapshot(db):
    with module.suggestion_session(7, source="notifications") as session_id:
        assert session_id == 42

    # `finalize_session` et pas `update_session` : lui seul agrege les interactions de
    # la session dans les colonnes stats_*. Sans ca la session resterait ACTIVE avec
    # des compteurs a zero alors que les follows sont bien en base.
    assert db.finalized[0]["session_id"] == 42
    assert db.finalized[0]["status"] == "COMPLETED"
    assert "duration_seconds" in db.finalized[0]


def test_an_interrupted_pass_is_closed_in_error_and_not_left_active(db):
    """Une session qui ne finit jamais fausse autant les moyennes qu'une manquante."""
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
    """Les metriques comptent, mais pas au point d'empecher le travail de se faire."""
    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr("taktik.core.database.local.service.get_local_database", _boom)

    with module.suggestion_session(7, source="notifications") as session_id:
        assert session_id is None  # on continue sans session plutot que d'echouer


def test_the_session_manager_carries_the_id_the_recorder_reads():
    """``_get_session_id()`` lit ``session_manager.session_id`` par ``hasattr`` — mais
    l'attribut n'existait nulle part, donc toute execution hors InstagramAutomation
    ecrivait ses interactions avec un session_id NULL."""
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
