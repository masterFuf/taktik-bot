"""Workflow runner for the Instagram Taktik Agent bridge."""

from __future__ import annotations

from bridges.instagram.agent.runtime.ai import build_agent_ai_service


def run_agent_workflow(*, app, device_manager, config: dict, ipc) -> dict:
    ipc.status("launching", "Launching Instagram\u2026")
    if not app.launch():
        ipc.error("Failed to launch Instagram", error_code="INSTAGRAM_LAUNCH_FAILED")
        return {"success": False, "error": "Failed to launch Instagram"}
    ipc.status("instagram_ready", "Instagram launched successfully")

    from taktik.core.agent.scenarios.instagram_feed_autopilot import TaktikAgentWorkflow

    workflow = TaktikAgentWorkflow(
        device_manager=device_manager,
        config=config,
        ipc=ipc,
        ai_service_factory=build_agent_ai_service,
    )

    from bridges.common.runtime import signal_handler as _sig

    _sig.update_workflow(workflow)
    return workflow.run()
