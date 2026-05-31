#!/usr/bin/env python3
"""
Account Bridge — TikTok Login / Register / Logout

Handles:
  - workflowType: "login"    → LoginWorkflow (connect existing account on device)
  - workflowType: "register" → SignupWorkflow (create new account on device)
  - workflowType: "logout"   → LogoutWorkflow (sign out current account)

Config JSON fields:
  For login:
    {
      "workflowType": "login",
      "deviceId": "...",
      "username": "...",
      "password": "...",
      "saveSession": true,
      "packageName": null
    }

  For logout:
    {
      "workflowType": "logout",
      "deviceId": "...",
      "packageName": null
    }

  For register:
    {
      "workflowType": "register",
      "deviceId": "...",
      "method": "email" | "phone",
      "email": "...",
      "phone": "...",
      "packageName": null
    }
"""

import os
import signal
import sys

# Bootstrap: UTF-8 + loguru + sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.tiktok.base import (
    _ipc,
    send_error,
    send_status,
)
from bridges.common.runtime.signal_handler import setup_signal_handlers
from bridges.tiktok.account.runtime.account_session import TikTokAccountSessionMixin
from bridges.tiktok.account.runtime.account_workflows import TikTokAccountWorkflowMixin


class TikTokAccountBridge(TikTokAccountWorkflowMixin, TikTokAccountSessionMixin):
    """Bridge for TikTok account management (login / logout / register)."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get('deviceId')
        self.workflow_type = config.get('workflowType')  # "login" | "logout" | "register"
        self.package_name = config.get('packageName')
        self._connection = None

        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum, frame):
        send_status("stopping", "Received shutdown signal")

    # ------------------------------------------------------------------
    # Entrypoint
    # ------------------------------------------------------------------

    def run(self) -> int:
        if not self.device_id:
            send_error("Device ID is required")
            return 1
        if not self.workflow_type:
            send_error("workflowType is required ('login', 'logout', or 'register')")
            return 1

        device = self._prepare_device()
        if device is None:
            return 1

        # Dispatch
        if self.workflow_type == "login":
            return self._run_login(device)
        elif self.workflow_type == "logout":
            return self._run_logout(device)
        elif self.workflow_type == "register":
            return self._run_register(device)
        else:
            send_error(f"Unknown workflowType: {self.workflow_type}")
            return 1


def main():
    from bridges.tiktok.account.runtime.account_commands import run_account_bridge_cli

    sys.exit(run_account_bridge_cli(sys.argv[1:]))


if __name__ == '__main__':
    main()
