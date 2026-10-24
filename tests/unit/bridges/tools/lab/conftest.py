"""The Lab opens the bot's base before every action, as a run does: each test of it gets one of its own."""

import pytest


@pytest.fixture(autouse=True)
def lab_base(monkeypatch, tmp_path):
    """A throwaway base for the Lab run (`TAKTIK_DB_PATH`), opened by whoever opens it first."""
    import taktik.core.database as database
    from taktik.core.database.local import service

    monkeypatch.setenv("TAKTIK_DB_PATH", str(tmp_path / "lab.db"))
    monkeypatch.setattr(database, "db_service", None)
    monkeypatch.setattr(service, "_local_db_instance", None)
    yield tmp_path / "lab.db"
    if service._local_db_instance is not None:
        service._local_db_instance.close()
