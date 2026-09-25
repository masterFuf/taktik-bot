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


def test_an_unknown_workflow_type_fails_after_the_restart(ig_rig):
    _check("notifications_refused", ig_rig, ig_rig.run_bridge(feed_payload(workflowType="notifications")))


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


def test_the_debug_mode_still_runs_the_desktop_debug_tool(ig_rig, monkeypatch):
    import sys

    from bridges.instagram.automation import desktop
    from bridges.instagram.diagnostics.debug import DebugBridge

    seen = []
    monkeypatch.setattr(DebugBridge, "run", lambda self: seen.append(dict(self.config)) or 0)
    monkeypatch.setattr(desktop, "setup_stats_callback", lambda: None)
    monkeypatch.setattr(sys, "argv", ["desktop_bridge", "--debug", "--mode", "detect", "--device", "emulator-5554"])

    with pytest.raises(SystemExit) as exit_info:
        desktop.main()

    assert exit_info.value.code == 0
    assert seen == [{"debugMode": True, "mode": "detect", "deviceId": "emulator-5554"}]
    assert "run_workflow" not in ig_rig.calls
