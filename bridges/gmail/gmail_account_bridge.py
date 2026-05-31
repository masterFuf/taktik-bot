#!/usr/bin/env python3
"""Gmail account bridge.

The bridge owns desktop concerns only: config loading, DB bootstrap, device
connection, cleanup and stdout JSON events. Gmail account operations live in
`taktik.core.app.email.gmail.workflows.account`.
"""

from __future__ import annotations

import json
import os
import signal
import sys


bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.bootstrap import setup_environment

setup_environment()

from bridges.common.connection import ConnectionService
from bridges.common.signal_handler import setup_signal_handlers
from bridges.gmail.base import _ipc, send_error, send_log, send_message, send_status
from taktik.core.app.email.gmail.workflows.account import GmailWorkflow


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

        try:
            from taktik.core.database import configure_db_service

            configure_db_service()
        except Exception as exc:  # noqa: BLE001 - bridge must emit JSON errors
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
            if self.workflow_type == "read_otp":
                return self._run_read_otp(device)
            if self.workflow_type == "scan_accounts":
                return self._run_scan_accounts(device)
            send_error(f"Unknown workflowType: {self.workflow_type}")
            return 1
        finally:
            from bridges.common.app_manager import force_stop_app

            force_stop_app(self.device_id, "gmail")

    def _run_login(self, device) -> int:
        email = (self.config.get("email") or "").strip()
        password = self.config.get("password") or ""
        if not email or not password:
            send_error("email and password are required for login")
            return 1

        send_status("running", f"Adding Gmail account {email}...")
        send_log("info", f"Gmail login workflow - {email}")

        try:
            workflow = GmailWorkflow(device, self.device_id, notifier=_ipc)
            result = workflow.ensure_account_added(email, password)
            if result.get("success"):
                self._persist_account(email)
            return self._finish_account_result(result, workflow_type="login", email=email)
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"Gmail login error: {exc}")
            send_log("error", traceback.format_exc())
            return 1

    def _run_logout(self, device) -> int:
        email = (self.config.get("email") or "").strip()
        if not email:
            send_error("email is required for logout")
            return 1

        send_status("running", f"Removing Gmail account {email}...")
        send_log("info", f"Gmail logout workflow - {email}")

        try:
            workflow = GmailWorkflow(device, self.device_id, notifier=_ipc)
            result = workflow.open_account_removal_settings(email=email)
            if result.get("success"):
                self._unpersist_account(email)
            return self._finish_account_result(result, workflow_type="logout", email=email)
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"Gmail logout error: {exc}")
            send_log("error", traceback.format_exc())
            return 1

    def _run_read_otp(self, device) -> int:
        email = (self.config.get("email") or "").strip()
        sender_filter = self.config.get("senderFilter") or None
        subject_filter = self.config.get("subjectFilter") or None
        timeout = int(self.config.get("timeout") or 120)
        if not email:
            send_error("email is required for read_otp")
            return 1

        send_status("running", f"Reading verification code from {email}...")
        send_log("info", f"Gmail OTP workflow - {email} (sender={sender_filter})")

        try:
            workflow = GmailWorkflow(device, self.device_id, notifier=_ipc)
            result = workflow.get_latest_verification_code(
                email=email,
                sender_filter=sender_filter,
                subject_filter=subject_filter,
                timeout=timeout,
            )
            return self._finish_account_result(
                result,
                workflow_type="read_otp",
                email=email,
                extra={"code": result.get("code")},
            )
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"Gmail OTP error: {exc}")
            send_log("error", traceback.format_exc())
            return 1

    def _run_scan_accounts(self, device) -> int:
        send_status("running", "Scanning Gmail accounts...")
        send_log("info", "Gmail scan_accounts workflow")

        try:
            workflow = GmailWorkflow(device, self.device_id, notifier=_ipc)
            result = workflow.scan_accounts()
            if result.get("success"):
                for account in result.get("accounts", []):
                    email = account.get("email") if isinstance(account, dict) else None
                    if email:
                        self._persist_account(email)
            success = bool(result.get("success"))
            send_status("success" if success else "error", result.get("message", ""))
            send_message(
                "account_result",
                success=success,
                workflow="scan_accounts",
                accounts=result.get("accounts", []),
                message=result.get("message", ""),
                error_type=result.get("error_type"),
            )
            return 0 if success else 1
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"Gmail scan_accounts error: {exc}")
            send_log("error", traceback.format_exc())
            return 1

    def _finish_account_result(
        self,
        result: dict,
        *,
        workflow_type: str,
        email: str,
        extra: dict | None = None,
    ) -> int:
        success = bool(result.get("success"))
        send_status("success" if success else "error", result.get("message", ""))
        payload = {
            "success": success,
            "workflow": workflow_type,
            "email": email,
            "message": result.get("message", ""),
            "error_type": result.get("error_type"),
        }
        if extra:
            payload.update(extra)
        send_message("account_result", **payload)
        return 0 if success else 1

    def _persist_account(self, email: str) -> None:
        from taktik.core.database.repositories.gmail import GmailAccountRepository

        if not GmailAccountRepository().upsert(email, self.device_id):
            send_log("warning", f"Could not persist Gmail account {email}")

    def _unpersist_account(self, email: str) -> None:
        from taktik.core.database.repositories.gmail import GmailAccountRepository

        if not GmailAccountRepository().delete(email):
            send_log("warning", f"Could not unpersist Gmail account {email}")


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"type": "error", "message": "Usage: gmail_account_bridge.py <config_path>"}))
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            config = json.load(file)
    except Exception as exc:  # noqa: BLE001
        send_error(f"Failed to load config: {exc}")
        sys.exit(1)

    bridge = GmailAccountBridge(config)
    sys.exit(bridge.run())


if __name__ == "__main__":
    main()
