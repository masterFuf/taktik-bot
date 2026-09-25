"""The desktop's For You run, frozen: what the bridge asks of the phone and what it prints.

The snapshot beside this file was recorded from the bridge before its launcher moved into the
Agent handler. Moving code must not move a gesture or an event the desktop reads: same device
calls, same stdout events in the same order, same workflow config, same exit code.
"""
import json
from dataclasses import asdict
from pathlib import Path

import pytest

SNAPSHOT = json.loads(
    (Path(__file__).parent / "tiktok_for_you_bridge_sequence.json").read_text(encoding="utf-8")
)
AI_KEY = "sk-or-v1-" + "a" * 48


def _observed(rig, code):
    return {
        "exit": code,
        "calls": rig.calls,
        "events": [[kind, payload] for kind, payload in rig.events],
        "config": asdict(rig.built_config),
        "ai_installs": rig.ai_installs,
        "ai_services": rig.ai_services,
    }


def _assert_matches(observed, expected):
    # JSON round trip: the snapshot holds what went over the wire, not Python types.
    observed = json.loads(json.dumps(observed))
    assert observed["calls"] == expected["calls"]
    assert observed["events"] == expected["events"]
    assert observed["config"] == expected["config"]
    assert observed["ai_installs"] == expected["ai_installs"]
    assert observed["ai_services"] == expected["ai_services"]
    assert observed["exit"] == expected["exit"]


def test_the_page_payload_runs_exactly_as_recorded(rig, page_payload):
    code = rig.run_bridge(page_payload())
    _assert_matches(_observed(rig, code), SNAPSHOT["plain"])


def test_an_ai_run_installs_its_hooks_at_the_recorded_moment(rig, page_payload):
    payload = page_payload(ai={"enabled": True, "profileAnalysis": True, "openrouterApiKey": AI_KEY},
                           language="fr")
    code = rig.run_bridge(payload)
    _assert_matches(_observed(rig, code), SNAPSHOT["ai"])


def test_no_permission_dialog_means_no_deny_and_no_log(rig, page_payload):
    rig.permission_visible = False
    code = rig.run_bridge(page_payload())
    _assert_matches(_observed(rig, code), SNAPSHOT["no_permission"])


def test_the_running_workflow_is_the_one_a_stop_signal_reaches(rig, page_payload):
    from bridges.common.runtime import signal_handler

    rig.run_bridge(page_payload())
    assert signal_handler._workflow is rig.workflows[-1]


@pytest.mark.parametrize("payload, message", [
    ({"workflowType": "for_you"}, "No device ID provided"),
])
def test_a_refused_start_reports_the_same_error(rig, payload, message):
    code = rig.run_bridge(payload)
    errors = [event for kind, event in rig.events if kind == "error"]
    assert code == 1
    assert errors and errors[0]["error"] == message
    assert "restart" not in rig.calls
