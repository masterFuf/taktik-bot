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
from bridges.gmail.account.runtime.persistence import (
    persist_gmail_account,
    unpersist_gmail_account,
)
from bridges.gmail.account.runtime.session import cleanup_gmail_app, prepare_gmail_session
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

        session = prepare_gmail_session(self.device_id, send_status, send_error)
        if not session:
            return 1
        self._connection = session.connection

        try:
            if self.workflow_type == "login":
                return self._run_login(session.device)
            if self.workflow_type == "logout":
                return self._run_logout(session.device)
            if self.workflow_type == "read_otp":
                return self._run_read_otp(session.device)
            if self.workflow_type == "scan_accounts":
                return self._run_scan_accounts(session.device)
            send_error(f"Unknown workflowType: {self.workflow_type}")
            return 1
        finally:
            cleanup_gmail_app(self.device_id)

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
                persist_gmail_account(email, self.device_id, send_log)
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
                unpersist_gmail_account(email, send_log)
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
                        persist_gmail_account(email, self.device_id, send_log)
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

def main() -> None:
    run_bridge_main(GmailAccountBridge, usage="gmail_account_bridge.py <config_path>")


if __name__ == "__main__":
    main()
