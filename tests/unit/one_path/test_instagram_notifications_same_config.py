"""One notifications command, one run: the desktop bridge and the CLI handler do the same thing.

`instagram.engagement.notifications` had no launcher: the scan, the per-row verbs and the batch
lived in the bridge. They are `run_instagram_notifications` now, which the bridge and the handler
registered under that id both call. The CLI's runtime here connects the same recording phone the
bridge does; what each host prints is its own business, the result is the same.
"""
from __future__ import annotations

import pytest

from taktik.core.kernel.contracts import WorkflowInvocation
from taktik.core.kernel.registry import WorkflowRegistry
from taktik.core.shared.device.network_door import NetworkUnreachableError
from taktik.core.social_media.instagram.workflows.notifications.agent_handler import (
    INSTAGRAM_NOTIFICATIONS_WORKFLOW_ID,
    register_instagram_notifications_handlers,
)

from instagram_notifications_rig import BOT, DEVICE_ID, _Bridge, notif_command


def _cli(rig, spec):
    def runtime(package_name):
        bridge = _Bridge(rig, DEVICE_ID, package_name)
        bridge.connect()
        return bridge

    registry = WorkflowRegistry()
    register_instagram_notifications_handlers(registry, instagram_notifications_runtime=runtime,
                                              instagram_ai_service=lambda ai_config: None)
    params = {key: value for key, value in spec.items() if key != "deviceId"}
    invocation = WorkflowInvocation(platform="instagram", workflow_id=INSTAGRAM_NOTIFICATIONS_WORKFLOW_ID,
                                    params=params)
    # The CLI hands every handler the phone's serial (`taktik workflows run --device`).
    return registry.resolve(INSTAGRAM_NOTIFICATIONS_WORKFLOW_ID)(invocation, {"deviceId": DEVICE_ID})


def _run_both(rig, spec):
    code = rig.run_bridge(spec)
    bridge_calls, bridge_result = list(rig.calls), rig.stdout_lines[-1]
    rig.calls.clear()
    rig.stdout_lines.clear()
    cli_result = _cli(rig, spec)
    return code, bridge_calls, bridge_result, list(rig.calls), cli_result


def test_a_scan_is_the_same_run_from_the_bridge_and_the_cli(ign_rig):
    code, bridge_calls, bridge_result, cli_calls, cli_result = _run_both(
        ign_rig, notif_command("scan", scroll=2, accountUsername=BOT, followSuggestions=1))

    assert code == 0
    assert cli_calls == bridge_calls
    assert "bridge restart_instagram" in cli_calls
    assert cli_result == bridge_result


def test_a_batch_is_the_same_run_from_the_bridge_and_the_cli(ign_rig):
    spec = notif_command("batch", accountUsername=BOT, followBackDailyCap=1, actions=[
        {"action": "like", "username": "fan_one"},
        {"action": "follow_back", "username": "fan_three"},
        {"action": "follow_back", "username": "fan_four"},
    ])
    code, bridge_calls, bridge_result, cli_calls, cli_result = _run_both(ign_rig, spec)

    assert code == 0
    assert cli_calls == bridge_calls
    assert "bridge restart_instagram" not in cli_calls
    assert cli_result == bridge_result
    assert cli_result["skipped"] == 2


def test_a_phone_without_network_reads_no_notification_from_either_path(ign_rig):
    """No route at all: a scan read the activity Instagram had cached, and a row verb tapped into a
    screen that could not answer. Neither path measured the network; both now refuse the command at
    the launcher's network door, once the phone is connected, before Instagram restarts."""
    ign_rig.network.cut()
    for spec in (notif_command("scan", scroll=2, accountUsername=BOT),
                 notif_command("accept", username="fan_one", accountUsername=BOT)):
        assert ign_rig.run_bridge(spec) == 1
        assert [fields.get("error_code") for kind, fields in ign_rig.events if kind == "error"] == ["NETWORK_UNREACHABLE"]
        assert ign_rig.stdout_lines[-1]["success"] is False
        # The last line the app reads carries the motive, for the page to say its sentence.
        assert ign_rig.stdout_lines[-1]["error_code"] == "NETWORK_UNREACHABLE"
        assert "bridge restart_instagram" not in ign_rig.calls and "bridge build_workflow" not in ign_rig.calls
        ign_rig.calls.clear()
        ign_rig.stdout_lines.clear()
        ign_rig.events.clear()

        with pytest.raises(NetworkUnreachableError):
            _cli(ign_rig, spec)
        assert "bridge restart_instagram" not in ign_rig.calls and "bridge build_workflow" not in ign_rig.calls
        ign_rig.calls.clear()


def test_both_paths_measure_the_network_once_before_a_scan(ign_rig):
    """One measure per command, from either host, once the phone is connected and before the scan's
    clean restart."""
    ign_rig.network.calls = ign_rig.calls
    spec = notif_command("scan", scroll=2, accountUsername=BOT)
    for run in (lambda: ign_rig.run_bridge(spec), lambda: _cli(ign_rig, spec)):
        run()
        measures = [call for call in ign_rig.calls if call.startswith("network_baseline ")]
        assert measures == [f"network_baseline {DEVICE_ID}"]
        measured = ign_rig.calls.index(measures[0])
        assert ign_rig.calls.index("bridge connect") < measured < ign_rig.calls.index("bridge restart_instagram")
        ign_rig.calls.clear()
        ign_rig.stdout_lines.clear()
