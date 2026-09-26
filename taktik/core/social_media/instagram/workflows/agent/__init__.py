"""The Taktik Agent on Instagram: one launcher for the desktop bridge, the CLI and the Agent registry."""

from taktik.core.social_media.instagram.workflows.agent.agent_handler import (
    INSTAGRAM_AGENT_WORKFLOW_ID,
    AgentRuntime,
    register_instagram_agent_handlers,
    run_instagram_agent,
)

__all__ = ["AgentRuntime", "INSTAGRAM_AGENT_WORKFLOW_ID", "register_instagram_agent_handlers", "run_instagram_agent"]
