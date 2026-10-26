"""The persona analysis connects to the clone its payload names, read the way every Instagram run reads it.

The bridge read `packageName` by hand (no `package_name`, no trimming): a payload that named the clone
under its CLI name, or with a space around it, analysed the official app's account, or no app at all.
It reads through `package_name_from_payload` (`workflows/common/startup.py`), the one reading.
"""
import json

import pytest

from bridges.instagram.persona import persona_commands
from bridges.instagram.persona.bridge import PersonaAnalysisBridge

CLONE = "com.taktik.ig1"


def _connected_package(monkeypatch, capsys, config) -> str:
    """The package the bridge holds when it connects; the run itself is not played."""
    seen = []
    monkeypatch.setattr("taktik.core.database.configure_db_service", lambda: None)
    monkeypatch.setattr(PersonaAnalysisBridge, "connect", lambda bridge: seen.append(bridge.package_name) or True)
    monkeypatch.setattr(PersonaAnalysisBridge, "run", lambda bridge: {"success": True, "data": {}})

    persona_commands.run_persona_analysis({"deviceId": "emulator-5554", "username": "alpha", **config})

    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1]) == {"success": True, "data": {}}
    assert len(seen) == 1
    return seen[0]


@pytest.mark.parametrize("named", [{"packageName": CLONE}, {"package_name": CLONE}, {"packageName": f" {CLONE} "}],
                         ids=["app_name", "cli_name", "padded"])
def test_the_clone_of_the_payload_is_the_one_connected(monkeypatch, capsys, named):
    assert _connected_package(monkeypatch, capsys, named) == CLONE


@pytest.mark.parametrize("named", [{}, {"packageName": "  "}], ids=["absent", "blank"])
def test_without_a_clone_the_installed_instagram_is_connected(monkeypatch, capsys, named):
    assert _connected_package(monkeypatch, capsys, named) == PersonaAnalysisBridge.DEFAULT_PACKAGE
