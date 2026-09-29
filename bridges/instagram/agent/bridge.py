"""The phone of an Instagram Taktik Agent session."""

from __future__ import annotations

from taktik.core.social_media.instagram.workflows.core.device import InstagramDeviceBase
from taktik.core.social_media.instagram.workflows.agent.agent_handler import AgentRuntime


class TaktikAgentBridge(InstagramDeviceBase):
    """The clone-aware Instagram device of the core, as the runtime the Agent's launcher asks for."""

    def agent_runtime(self) -> AgentRuntime:
        """The connected device and the clean restart of Instagram through `AppService`."""
        return AgentRuntime(device_manager=self.device_manager, restart=self._app.restart)


__all__ = ["TaktikAgentBridge"]
