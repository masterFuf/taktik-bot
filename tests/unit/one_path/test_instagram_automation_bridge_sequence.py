"""The desktop's Instagram automation run, frozen: what the bridge asks of the phone and prints.

The snapshot beside this file was recorded from `desktop_bridge` before its run moved into the
core launcher shared with the CLI. Moving code must not move a gesture or an event the desktop
reads: same device calls, same stdout events in the same order, same workflow config, same AI
hooks, same exit code. Set TAKTIK_RECORD_SNAPSHOT=1 to record it again, on purpose only.
"""
import json
import os
from pathlib import Path

import pytest

from instagram_rig import AI_KEY, feed_payload, target_payload

SNAPSHOT_PATH = Path(__file__).parent / "instagram_automation_bridge_sequence.json"
RECORD = os.environ.get("TAKTIK_RECORD_SNAPSHOT") == "1"
SNAPSHOT = {} if RECORD else json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _observed(rig, code) -> dict:
    config_path = str(rig.tmp_path / "instagram_config.json")
    events = []
    for kind, payload in rig.events:
        payload = dict(payload)
        # A traceback names the frames it went through, which moving code changes by design.
        if "traceback" in payload:
            payload["traceback"] = "<traceback>"
        events.append([kind, payload])
    observed = {
        "exit": code,
        "calls": rig.calls,
        "events": events,
        "config": rig.built_config,
        "ai_services": rig.ai_services,
        "ai_installs": rig.ai_installs,
    }
    # JSON round trip: the snapshot holds what went over the wire, not Python types.
    text = json.dumps(observed, default=str).replace(json.dumps(config_path)[1:-1], "<config>")
    return json.loads(text)


def _check(name, rig, code) -> None:
    observed = _observed(rig, code)
    if RECORD:
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8")) if SNAPSHOT_PATH.exists() else {}
        snapshot[name] = observed
        SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return
    expected = SNAPSHOT[name]
    assert observed["calls"] == expected["calls"]
    assert observed["events"] == expected["events"]
    assert observed["config"] == expected["config"]
    assert observed["ai_services"] == expected["ai_services"]
    assert observed["ai_installs"] == expected["ai_installs"]
    assert observed["exit"] == expected["exit"]


def test_the_feed_page_payload_runs_exactly_as_recorded(ig_rig):
    _check("feed", ig_rig, ig_rig.run_bridge(feed_payload()))


def test_a_target_run_with_ai_installs_its_hooks_at_the_recorded_moment(ig_rig):
    payload = target_payload(ai={"enabled": True, "profileAnalysis": True, "openrouterApiKey": AI_KEY})
    _check("target_ai", ig_rig, ig_rig.run_bridge(payload))


def test_a_clone_package_is_launched_and_patched_as_recorded(ig_rig):
    _check("clone", ig_rig, ig_rig.run_bridge(feed_payload(packageName="com.taktik.ig1")))


def test_instagram_missing_stops_before_the_run(ig_rig):
    ig_rig.installed = False
    _check("not_installed", ig_rig, ig_rig.run_bridge(feed_payload()))


def test_a_failed_launch_stops_before_the_run(ig_rig):
    ig_rig.launch_ok = False
    _check("launch_failed", ig_rig, ig_rig.run_bridge(feed_payload()))


def test_a_workflow_that_raises_reports_it_and_stops_the_app(ig_rig):
    ig_rig.workflow_raises = RuntimeError("feed screen not reached")
    _check("workflow_error", ig_rig, ig_rig.run_bridge(feed_payload()))


def test_an_unknown_workflow_type_is_refused_before_the_phone_is_touched(ig_rig):
    # Re-recorded three times on 2026-10-18. The launcher first read its payload before the restart;
    # then the bridge's entry read it before the bridge was built; the launcher now reads it before it
    # asks the bridge for the phone (`connect`), so the bridge's start lines come first again. No
    # connection, no rotation, no app stop, the same error sentence and code, exit 1 (5 before, which
    # the app does not tell apart), and no traceback: a refusal is not a crash.
    _check("notifications_refused", ig_rig, ig_rig.run_bridge(feed_payload(workflowType="notifications")))


def _phone_calls(calls) -> dict:
    """The connections, IP rotations and app stops among the calls the rig recorded."""
    return {
        "connections": [call for call in calls if call.startswith("connect ")],
        "ip_rotations": [call for call in calls if call.startswith("ip_rotation ")],
        "app_stops": [call for call in calls if call.startswith("stop ")],
    }


def test_a_setting_out_of_its_bounds_is_refused_before_the_phone_is_touched(ig_rig):
    # A fresh IP asked for: the refusal comes before the rotation, before the connection, and the
    # bridge leaves the app alone.
    limits = dict(feed_payload()["limits"], maxProfiles=501)
    code = ig_rig.run_bridge(feed_payload(limits=limits, networkReset={"enabled": True, "method": "airplane_cell"}))

    assert code != 0
    assert _phone_calls(ig_rig.calls) == {"connections": [], "ip_rotations": [], "app_stops": []}
    assert ig_rig.calls == ["stats_callback"]
    # The line the app reads, as before: its sentence and its code.
    errors = [(payload["error"], payload["error_code"]) for kind, payload in ig_rig.events if kind == "error"]
    assert errors == [(
        "Workflow error: Refused before the phone is touched: limits.maxProfiles = 501, outside its bounds (1 to 500)",
        "WORKFLOW_ERROR",
    )]


def test_a_setting_inside_its_bounds_still_rotates_then_runs(ig_rig):
    code = ig_rig.run_bridge(feed_payload(networkReset={"enabled": True, "method": "airplane_cell"}))

    assert code == 0
    calls = ig_rig.calls
    assert calls.index("connect emulator-5554") < calls.index("ip_rotation airplane_cell") < calls.index("run_workflow")
    assert calls[-1] == "stop com.instagram.android"


def test_a_device_that_does_not_connect_stops_everything(ig_rig):
    ig_rig.connect_ok = False
    _check("no_connection", ig_rig, ig_rig.run_bridge(feed_payload()))


@pytest.mark.parametrize("name, overrides", [
    ("no_device", {"deviceId": None}),
    ("no_workflow_type", {"workflowType": None}),
    ("no_target", {"target": ""}),
])
def test_a_refused_start_reports_the_same_error(ig_rig, name, overrides):
    _check(name, ig_rig, ig_rig.run_bridge(feed_payload(**overrides)))


def test_the_debug_mode_still_runs_the_desktop_debug_tool(ig_rig, monkeypatch, tmp_path):
    """The desktop's debug capture: the same config file entry, `debugMode` picks the tool."""
    import json
    import sys

    from bridges.instagram.automation import desktop_bridge as desktop
    from bridges.instagram.automation.debug import DebugBridge

    seen = []
    monkeypatch.setattr(DebugBridge, "run", lambda self: seen.append(dict(self.config)) or 0)
    monkeypatch.setattr(desktop, "setup_stats_callback", lambda: None)
    config_path = tmp_path / "debug.json"
    config_path.write_text(json.dumps({"debugMode": True, "mode": "detect", "deviceId": "emulator-5554"}),
                           encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["desktop_bridge", str(config_path)])

    with pytest.raises(SystemExit) as exit_info:
        desktop.main()

    assert exit_info.value.code == 0
    assert seen == [{"debugMode": True, "mode": "detect", "deviceId": "emulator-5554"}]
    assert "run_workflow" not in ig_rig.calls
