#!/usr/bin/env python3
"""YouTube account bridge.

The bridge owns desktop concerns only: config loading, device connection, DB
bootstrap and stdout JSON events. The durable YouTube account flow lives in
`taktik.core.social_media.youtube.workflows.account`.
"""

from __future__ import annotations

import os
import signal
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.bootstrap import setup_environment

setup_environment()

from bridges.common.device.connection import ConnectionService
from bridges.common.runtime.entrypoint import run_bridge_main
from bridges.common.runtime.signal_handler import setup_signal_handlers
from bridges.youtube.base import _ipc, send_error, send_log, send_message, send_status
from taktik.core.social_media.youtube.workflows.account import YouTubeAccountWorkflow


class YouTubeAccountBridge:
    """Bridge for YouTube account login/logout workflows."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self.workflow_type = config.get("workflowType", "login")
        self._connection = None

        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, _signum, _frame) -> None:
        send_status("stopping", "Received shutdown signal")

    def run(self) -> int:
        if not self.device_id:
            send_error("deviceId is required")
            return 1

        try:
            from taktik.core.database import configure_db_service

            configure_db_service()
        except Exception as exc:  # noqa: BLE001 - bridge must return JSON errors
            send_error(f"Database setup failed: {exc}")
            return 1

        send_status("connecting", f"Connecting to device {self.device_id}...")
        self._connection = ConnectionService(self.device_id)
        if not self._connection.connect():
            send_error(f"Failed to connect to device {self.device_id}")
            return 1

        device = self._connection.device
        if not device:
            send_error("Device object unavailable after connection")
            return 1

        try:
            if self.workflow_type == "login":
                return self._run_login(device)
            if self.workflow_type == "logout":
                return self._run_logout(device)
            send_error(f"Unknown workflowType: {self.workflow_type}")
            return 1
        finally:
            from bridges.common.device.app_manager import force_stop_app

            force_stop_app(self.device_id, "youtube")

    def _run_login(self, device) -> int:
        email = (self.config.get("email") or "").strip()
        if not email:
            send_error("email is required for YouTube login")
            return 1

        workflow = YouTubeAccountWorkflow(device, self.device_id, notifier=_ipc)
        result = workflow.login(
            email=email,
            password=(self.config.get("password") or ""),
        )
        return self._finish_account_result(result, workflow_type="login", email=email)

    def _run_logout(self, device) -> int:
        email = (self.config.get("email") or "").strip()
        workflow = YouTubeAccountWorkflow(device, self.device_id, notifier=_ipc)
        result = workflow.logout(email=email)
        return self._finish_account_result(result, workflow_type="logout", email=email)

    def _finish_account_result(
        self,
        result: dict,
        *,
        workflow_type: str,
        email: str,
    ) -> int:
        success = bool(result.get("success"))
        message = result.get("message", "")
        if success:
            send_status("success", message)
            send_message(
                "account_result",
                success=True,
                workflow=workflow_type,
                email=email,
                message=message,
            )
            return 0

        send_status("error", message)
        send_error(message or f"YouTube {workflow_type} failed")
        if result.get("error_type"):
            send_log("debug", f"YouTube {workflow_type} error_type={result['error_type']}")
        return 1


def main() -> None:
    run_bridge_main(YouTubeAccountBridge, usage="youtube_account_bridge.py <config_path>")


if __name__ == "__main__":
    main()
