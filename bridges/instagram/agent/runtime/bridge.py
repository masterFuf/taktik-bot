"""The phone of an Instagram Taktik Agent session."""

from __future__ import annotations

from bridges.instagram.runtime.bridge import InstagramBridgeBase
from taktik.core.social_media.instagram.workflows.agent.agent_handler import AgentRuntime


class TaktikAgentBridge(InstagramBridgeBase):
    """The bridges' clone-aware Instagram connection, as the runtime the Agent's launcher asks for."""

    def agent_runtime(self) -> AgentRuntime:
        """The connected device and the clean restart of Instagram through `AppService`."""
        return AgentRuntime(device_manager=self.device_manager, restart=self._app.restart)


__all__ = ["TaktikAgentBridge"]
