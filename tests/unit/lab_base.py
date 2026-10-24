"""A throwaway base for a Lab run: the Lab opens the bot's base before every action, as a run does."""

import taktik.core.database as database
from taktik.core.database.local import service


def give_the_lab_a_base(monkeypatch, tmp_path):
    """Point `TAKTIK_DB_PATH` at a base of the test's own, opened by whoever opens it first; returns
    its path. Close it with `close_the_lab_base` once the test is over."""
    monkeypatch.setenv("TAKTIK_DB_PATH", str(tmp_path / "lab.db"))
    monkeypatch.setattr(database, "db_service", None)
    monkeypatch.setattr(service, "_local_db_instance", None)
    return tmp_path / "lab.db"


def close_the_lab_base():
    if service._local_db_instance is not None:
        service._local_db_instance.close()
