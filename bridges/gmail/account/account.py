#!/usr/bin/env python3
"""Gmail account bridge.

The bridge owns desktop concerns only: config loading, DB bootstrap, device
connection, cleanup and stdout JSON events. Gmail account operations live in
`taktik.core.app.email.gmail.workflows.account`.
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
from bridges.gmail.account.runtime.session import cleanup_gmail_app, prepare_gmail_session
from bridges.gmail.account.runtime.workflows import (
    run_gmail_login,
    run_gmail_logout,
    run_gmail_read_otp,
    run_gmail_scan_accounts,
)
from bridges.gmail.base import _ipc, send_error, send_log, send_message, send_status


class GmailAccountBridge:
    """Bridge for Gmail account management."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self.workflow_type = config.get("workflowType")
        self._connection = None

        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, _signum, _frame) -> None:
        send_status("stopping", "Received shutdown signal")

    def run(self) -> int:
        if not self.device_id:
            send_error("Device ID is required")
            return 1
        if not self.workflow_type:
            send_error("workflowType is required ('login', 'logout', 'read_otp', or 'scan_accounts')")
            return 1

        session = prepare_gmail_session(self.device_id, send_status, send_error)
        if not session:
            return 1
        self._connection = session.connection

        try:
            if self.workflow_type == "login":
                return run_gmail_login(
                    config=self.config,
                    device=session.device,
                    device_id=self.device_id,
                    notifier=_ipc,
                    send_status=send_status,
                    send_log=send_log,
                    send_error=send_error,
                    send_message=send_message,
                )
            if self.workflow_type == "logout":
                return run_gmail_logout(
                    config=self.config,
                    device=session.device,
                    device_id=self.device_id,
                    notifier=_ipc,
                    send_status=send_status,
                    send_log=send_log,
                    send_error=send_error,
                    send_message=send_message,
                )
            if self.workflow_type == "read_otp":
                return run_gmail_read_otp(
                    config=self.config,
                    device=session.device,
                    device_id=self.device_id,
                    notifier=_ipc,
                    send_status=send_status,
                    send_log=send_log,
                    send_error=send_error,
                    send_message=send_message,
                )
            if self.workflow_type == "scan_accounts":
                return run_gmail_scan_accounts(
                    device=session.device,
                    device_id=self.device_id,
                    notifier=_ipc,
                    send_status=send_status,
                    send_log=send_log,
                    send_error=send_error,
                    send_message=send_message,
                )
            send_error(f"Unknown workflowType: {self.workflow_type}")
            return 1
        finally:
            cleanup_gmail_app(self.device_id)

def main() -> None:
    run_bridge_main(GmailAccountBridge, usage="gmail_account_bridge.py <config_path>")


if __name__ == "__main__":
    main()
