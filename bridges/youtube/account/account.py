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

from bridges.common.runtime.entrypoint import run_bridge_main
from bridges.common.runtime.signal_handler import setup_signal_handlers
from bridges.youtube.account.runtime.workflows import run_youtube_account_login, run_youtube_account_logout
from bridges.youtube.base import _ipc, send_error, send_status
from bridges.youtube.runtime.session import cleanup_youtube_app, prepare_youtube_session


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

        session = prepare_youtube_session(self.device_id, send_status, send_error)
        if not session:
            return 1
        self._connection = session.connection

        try:
            if self.workflow_type == "login":
                return run_youtube_account_login(self.config, device=session.device, device_id=self.device_id)
            if self.workflow_type == "logout":
                return run_youtube_account_logout(self.config, device=session.device, device_id=self.device_id)
            send_error(f"Unknown workflowType: {self.workflow_type}")
            return 1
        finally:
            cleanup_youtube_app(self.device_id)


def main() -> None:
    run_bridge_main(YouTubeAccountBridge, usage="youtube_account_bridge.py <config_path>")


if __name__ == "__main__":
    main()
