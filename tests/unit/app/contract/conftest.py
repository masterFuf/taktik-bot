"""The contract tests read the payload alone: a key in the environment would stand in for one."""

import pytest


@pytest.fixture(autouse=True)
def _no_openrouter_key_in_the_environment(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
