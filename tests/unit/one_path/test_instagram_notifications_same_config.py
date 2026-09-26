"""One notifications command, one run: the desktop bridge and the CLI handler do the same thing.

`instagram.engagement.notifications` had no launcher: the scan, the per-row verbs and the batch
lived in the bridge. They are `run_instagram_notifications` now, which the bridge and the handler
registered under that id both call. The CLI's runtime here connects the same recording phone the
bridge does; what each host prints is its own business, the result is the same.
"""
from __future__ import annotations

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowRegistry
from taktik.core.social_media.instagram.workflows.management.notifications.agent_handler import (
    INSTAGRAM_NOTIFICATIONS_WORKFLOW_ID,
    register_instagram_notifications_handlers,
)

from instagram_notifications_rig import BOT, DEVICE_ID, _Bridge, notif_command


def _cli(rig, spec):
    def runtime(package_name, restart):
        bridge = _Bridge(rig, DEVICE_ID, package_name)
        bridge.connect()
        if restart:
            bridge.restart_instagram()
        return bridge

    registry = WorkflowRegistry()
    register_instagram_notifications_handlers(registry, instagram_notifications_runtime=runtime,
                                              instagram_ai_service=lambda ai_config: None)
    params = {key: value for key, value in spec.items() if key != "deviceId"}
    invocation = WorkflowInvocation(platform="instagram", workflow_id=INSTAGRAM_NOTIFICATIONS_WORKFLOW_ID,
                                    params=params)
    return registry.resolve(INSTAGRAM_NOTIFICATIONS_WORKFLOW_ID)(invocation, {})


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
