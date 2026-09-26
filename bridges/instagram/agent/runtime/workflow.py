"""Workflow runner for the Instagram Taktik Agent bridge."""

from __future__ import annotations

from bridges.instagram.agent.runtime.ai import build_agent_ai_service
from taktik.core.social_media.instagram.workflows.agent.agent_handler import run_instagram_agent


def run_agent_workflow(*, app, device_manager, config: dict, ipc) -> dict:
    """The core launcher, with the bridge's restart, AI factory and stop registration."""
    from bridges.common.runtime import signal_handler as _sig

    return run_instagram_agent(
        config,
        device_manager=device_manager,
        restart=app.restart,
        ipc=ipc,
        ai_service_factory=build_agent_ai_service,
        on_workflow=_sig.update_workflow,
    )
