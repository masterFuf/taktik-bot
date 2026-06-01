"""Instagram account bridge runtime class."""

from __future__ import annotations

import signal

from bridges.common.runtime.signal_handler import setup_signal_handlers
from bridges.instagram.account.runtime.session import AccountSessionLifecycleMixin
from bridges.instagram.account.runtime.workflows import AccountWorkflowRunnerMixin
from bridges.instagram.runtime.ipc import _ipc, send_error, send_status


class AccountBridge(AccountSessionLifecycleMixin, AccountWorkflowRunnerMixin):
    """Bridge for Instagram account management (login / register / logout)."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get("deviceId")
        self.workflow_type = config.get("workflowType")
        self.package_name = config.get("packageName")
        self._connection = None

        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum, frame):
        send_status("stopping", "Received shutdown signal")

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

        if self.workflow_type == "login":
            return self._run_login(device)
        if self.workflow_type == "register":
            return self._run_register(device)
        if self.workflow_type == "logout":
            return self._run_logout(device)

        send_error(f"Unknown workflowType: {self.workflow_type}")
        return 1


__all__ = ["AccountBridge"]
