"""The desktop's Taktik Agent bridge, frozen: how it prepares the phone and starts the Agent.

The snapshot beside this file was recorded from `taktik_agent_bridge` while its start sequence (the
clean restart, the status lines, the workflow built with the bridge's AI factory) still lived in
the bridge. It moved into the core launcher the CLI shares: none of that may move. Set
TAKTIK_RECORD_SNAPSHOT=1 to record it again, on purpose only.
"""
import json
import os
from pathlib import Path

import pytest

from instagram_agent_rig import CLONE, agent_config

SNAPSHOT_PATH = Path(__file__).parent / "instagram_agent_bridge_sequence.json"
RECORD = os.environ.get("TAKTIK_RECORD_SNAPSHOT") == "1"
SNAPSHOT = {} if RECORD else json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _observed(rig, code) -> dict:
    config_path = str(rig.tmp_path / "agent_config.json")
    observed = {"exit": code, "calls": rig.calls, "stdout": rig.stdout_lines,
                "events": [[kind, payload] for kind, payload in rig.events], "workflows": rig.workflows}
    text = json.dumps(observed, default=str).replace(json.dumps(config_path)[1:-1], "<config>")
    return json.loads(text)


def _check(name, rig, code) -> None:
    observed = _observed(rig, code)
    if RECORD:
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8")) if SNAPSHOT_PATH.exists() else {}
        snapshot[name] = observed
        SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    assert observed == SNAPSHOT[name]


@pytest.fixture(autouse=True)
def _guard(no_phone):
    return no_phone


def test_a_session_restarts_instagram_then_runs_the_agent(iga_rig):
    _check("default", iga_rig, iga_rig.run_agent_bridge(agent_config()))


def test_a_clone_is_restarted_on_its_package(iga_rig):
    _check("clone", iga_rig, iga_rig.run_agent_bridge(agent_config(packageName=CLONE)))


def test_a_failed_session_exits_non_zero(iga_rig):
    iga_rig.run_result = {"success": False, "error": "no AI"}
    _check("failed", iga_rig, iga_rig.run_agent_bridge(agent_config()))


def test_instagram_that_does_not_start_stops_the_session(iga_rig, monkeypatch):
    monkeypatch.setattr(type(iga_rig.device_manager), "launch_app",
                        lambda self, package, activity=None, stop_first=False:
                        iga_rig.calls.append(f"launch {package} failed") or False)
    _check("no_launch", iga_rig, iga_rig.run_agent_bridge(agent_config()))


def test_a_device_that_does_not_connect_stops_the_session(iga_rig):
    iga_rig.connect_ok = False
    _check("no_connection", iga_rig, iga_rig.run_agent_bridge(agent_config()))


def test_no_config_file_is_refused(iga_rig):
    _check("no_argument", iga_rig, iga_rig.run_agent_bridge(None, argv=["taktik_agent_bridge"]))
