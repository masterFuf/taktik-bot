"""Instagram Taktik Agent bridge runtime class."""

from __future__ import annotations

from loguru import logger

from bridges.instagram.agent.runtime.stop_listener import start_agent_stop_listener
from bridges.instagram.agent.runtime.workflow import run_agent_workflow
from bridges.instagram.runtime.bridge import InstagramBridgeBase
from bridges.instagram.runtime.ipc import _ipc


class TaktikAgentBridge(InstagramBridgeBase):
    """Bridge that launches the autonomous Taktik Agent workflow."""

    def __init__(self, device_id: str, config: dict, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self.config = config

    def run(self):
        # Electron can request a graceful stop via stdin: {"command":"stop"}.
        start_agent_stop_listener()
        result = run_agent_workflow(
            app=self._app,
            device_manager=self.device_manager,
            config=self.config,
            ipc=_ipc,
        )
        logger.info(f"[TaktikAgentBridge] Session finished: {result}")
        return result


__all__ = ["TaktikAgentBridge"]
