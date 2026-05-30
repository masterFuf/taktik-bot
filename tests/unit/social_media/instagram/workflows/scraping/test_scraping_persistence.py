from taktik.core.social_media.instagram.workflows.scraping.persistence import ScrapingPersistenceMixin


class _Workflow(ScrapingPersistenceMixin):
    pass


def test_local_db_accessor_caches_service(monkeypatch):
    workflow = _Workflow()
    fake_db = object()
    calls = []

    def fake_get_local_database():
        calls.append("called")
        return fake_db

    monkeypatch.setattr(
        "taktik.core.social_media.instagram.workflows.scraping.persistence.get_local_database",
        fake_get_local_database,
    )

    first = workflow._local_db()
    second = workflow._local_db()

    assert first is fake_db
    assert second is fake_db
    assert workflow.local_db is fake_db
    assert calls == ["called"]


def test_local_db_accessor_reuses_injected_service():
    workflow = _Workflow()
    workflow.local_db = object()

    assert workflow._local_db() is workflow.local_db
