"""The Lab opens the bot's base before every action, as a run does: each test of it gets one of its own."""

import pytest

from unit.lab_base import close_the_lab_base, give_the_lab_a_base


@pytest.fixture(autouse=True)
def lab_base(monkeypatch, tmp_path):
    """A throwaway base for the Lab run (`TAKTIK_DB_PATH`)."""
    yield give_the_lab_a_base(monkeypatch, tmp_path)
    close_the_lab_base()
