#!/usr/bin/env python3
"""
Account Bridge — Instagram Login / Register / Logout

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
      "saveLoginInfoInstagram": false,
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

import sys
import os
import json
import signal

# Bootstrap: UTF-8 + loguru + sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.instagram.runtime.ipc import (
    _ipc,
    send_status, send_error,
)
from bridges.instagram.account.runtime.session import AccountSessionLifecycleMixin
from bridges.instagram.account.runtime.workflows import AccountWorkflowRunnerMixin
from bridges.common.runtime.signal_handler import setup_signal_handlers


class AccountBridge(AccountSessionLifecycleMixin, AccountWorkflowRunnerMixin):
    """Bridge for Instagram account management (login / register)."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get('deviceId')
        self.workflow_type = config.get('workflowType')  # "login" | "register"
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
            send_error("workflowType is required ('login' or 'register')")
            return 1

        device = self._prepare_runtime_session()
        if device is None:
            return 1

        # Dispatch
        if self.workflow_type == "login":
            return self._run_login(device)
        elif self.workflow_type == "register":
            return self._run_register(device)
        elif self.workflow_type == "logout":
            return self._run_logout(device)
        else:
            send_error(f"Unknown workflowType: {self.workflow_type}")
            return 1

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"type": "error", "message": "Usage: account_bridge.py <config_path>"}))
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        send_error(f"Failed to load config: {e}")
        sys.exit(1)

    bridge = AccountBridge(config)
    sys.exit(bridge.run())


if __name__ == '__main__':
    main()
