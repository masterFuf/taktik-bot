#!/usr/bin/env python3
"""
Account Bridge — Gmail Login / Logout / Read OTP

Handles:
  - workflowType: "login"        → ensure_account_added (add a Google account to Gmail)
  - workflowType: "logout"       → remove a Google account from Gmail
  - workflowType: "read_otp"     → read latest verification code from a given inbox
  - workflowType: "scan_accounts" → list all Gmail accounts configured on the device

Config JSON fields:
  For login (add account):
    {
      "workflowType": "login",
      "deviceId": "...",
      "email": "...",
      "password": "..."
    }

  For logout (remove account):
    {
      "workflowType": "logout",
      "deviceId": "...",
      "email": "..."
    }

  For read_otp:
    {
      "workflowType": "read_otp",
      "deviceId": "...",
      "email": "...",
      "senderFilter": "TikTok",
      "subjectFilter": "verification",
      "timeout": 120
    }
"""

import sys
import os
import json
import signal

# Bootstrap: UTF-8 + loguru + sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.gmail.base import (
    logger, _ipc,
    send_message, send_status, send_error, send_log,
)
from bridges.common.connection import ConnectionService
from bridges.common.signal_handler import setup_signal_handlers


class GmailAccountBridge:
    """Bridge for Gmail account management (login / logout / read_otp)."""

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get('deviceId')
        self.workflow_type = config.get('workflowType')  # "login" | "logout" | "read_otp" | "scan_accounts"
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
            send_error("workflowType is required ('login', 'logout', 'read_otp', or 'scan_accounts')")
            return 1

        # Setup DB
        try:
            from taktik.core.database import configure_db_service
            configure_db_service()
        except Exception as e:
            send_error(f"Database setup failed: {e}")
            return 1

        # Connect
        send_status("connecting", f"Connecting to device {self.device_id}...")
        self._connection = ConnectionService(self.device_id)
        if not self._connection.connect():
            send_error(f"Failed to connect to device {self.device_id}")
            return 1

        device = self._connection.device
        if not device:
            send_error("Device object unavailable after connection")
            return 1

        # Dispatch
        try:
            if self.workflow_type == "login":
                return self._run_login(device)
            elif self.workflow_type == "logout":
                return self._run_logout(device)
            elif self.workflow_type == "read_otp":
                return self._run_read_otp(device)
            elif self.workflow_type == "scan_accounts":
                return self._run_scan_accounts(device)
            else:
                send_error(f"Unknown workflowType: {self.workflow_type}")
                return 1
        finally:
            from bridges.common.app_manager import force_stop_app
            force_stop_app(self.device_id, "gmail")

    # ------------------------------------------------------------------
    # Login (add account)
    # ------------------------------------------------------------------

    def _run_login(self, device) -> int:
        email = (self.config.get('email') or '').strip()
        password = self.config.get('password') or ''

        if not email or not password:
            send_error("email and password are required for login")
            return 1

        send_status("running", f"Adding Gmail account {email}…")
        send_log("info", f"📧 Gmail login workflow — {email}")

        try:
            from taktik.core.email.gmail.workflows.account import GmailWorkflow
            workflow = GmailWorkflow(device, self.device_id, notifier=_ipc)
            result = workflow.ensure_account_added(email, password)
            outcome = "success" if result.get('success') else "error"
            send_status(outcome, result.get('message', ''))
            send_message("account_result",
                         success=result.get('success', False),
                         workflow="login",
                         email=email,
                         message=result.get('message', ''),
                         error_type=result.get('error_type'))

            # Persist to local DB on success
            if result.get('success'):
                self._persist_account(email)

            return 0 if result.get('success') else 1
        except Exception as e:
            import traceback
            send_error(f"Gmail login error: {e}")
            send_log("error", traceback.format_exc())
            return 1

    # ------------------------------------------------------------------
    # Logout (remove account)
    # ------------------------------------------------------------------

    def _run_logout(self, device) -> int:
        email = (self.config.get('email') or '').strip()
        if not email:
            send_error("email is required for logout")
            return 1

        send_status("running", f"Removing Gmail account {email}…")
        send_log("info", f"🚪 Gmail logout workflow — {email}")

        try:
            from taktik.core.email.gmail.workflows.account import GmailWorkflow
            workflow = GmailWorkflow(device, self.device_id, notifier=_ipc)
            # Logout flow not yet implemented in GmailWorkflow — fall back to
            # opening Android Settings → Accounts so the user can confirm
            # removal manually.  We still mark as success at the bridge level
            # and let the UI handle confirmation.
            send_log("warning", "⚠️ Automatic Gmail logout not yet implemented. Opening Settings…")
            try:
                device.shell("am start -a android.settings.SYNC_SETTINGS")
            except Exception:
                pass

            self._unpersist_account(email)
            send_status("success", f"Gmail account {email} marked for removal")
            send_message("account_result",
                         success=True,
                         workflow="logout",
                         email=email,
                         message="Account marked for removal — confirm in Android Settings",
                         error_type=None)
            return 0
        except Exception as e:
            import traceback
            send_error(f"Gmail logout error: {e}")
            send_log("error", traceback.format_exc())
            return 1

    # ------------------------------------------------------------------
    # Read OTP (verification code from inbox)
    # ------------------------------------------------------------------

    def _run_read_otp(self, device) -> int:
        email = (self.config.get('email') or '').strip()
        sender_filter = self.config.get('senderFilter') or None
        subject_filter = self.config.get('subjectFilter') or None
        timeout = int(self.config.get('timeout') or 120)

        if not email:
            send_error("email is required for read_otp")
            return 1

        send_status("running", f"Reading verification code from {email}…")
        send_log("info", f"📬 Gmail OTP workflow — {email} (sender={sender_filter})")

        try:
            from taktik.core.email.gmail.workflows.account import GmailWorkflow
            workflow = GmailWorkflow(device, self.device_id, notifier=_ipc)
            result = workflow.get_latest_verification_code(
                email=email,
                sender_filter=sender_filter,
                subject_filter=subject_filter,
                timeout=timeout,
            )
            outcome = "success" if result.get('success') else "error"
            send_status(outcome, result.get('message', ''))
            send_message("account_result",
                         success=result.get('success', False),
                         workflow="read_otp",
                         email=email,
                         code=result.get('code'),
                         message=result.get('message', ''),
                         error_type=result.get('error_type'))
            return 0 if result.get('success') else 1
        except Exception as e:
            import traceback
            send_error(f"Gmail OTP error: {e}")
            send_log("error", traceback.format_exc())
            return 1

    # ------------------------------------------------------------------
    # Scan accounts
    # ------------------------------------------------------------------

    def _run_scan_accounts(self, device) -> int:
        send_status("running", "Scanning Gmail accounts…")
        send_log("info", "🔍 Gmail scan_accounts workflow")

        try:
            from taktik.core.email.gmail.workflows.account import GmailWorkflow
            workflow = GmailWorkflow(device, self.device_id, notifier=_ipc)
            result = workflow.scan_accounts()
            outcome = "success" if result.get('success') else "error"
            send_status(outcome, result.get('message', ''))
            # Persist each discovered account to the local DB
            if result.get('success'):
                for acc in result.get('accounts', []):
                    email = acc.get('email') or ''
                    if email:
                        self._persist_account(email)
            send_message("account_result",
                         success=result.get('success', False),
                         workflow="scan_accounts",
                         accounts=result.get('accounts', []),
                         message=result.get('message', ''),
                         error_type=result.get('error_type'))
            return 0 if result.get('success') else 1
        except Exception as e:
            import traceback
            send_error(f"Gmail scan_accounts error: {e}")
            send_log("error", traceback.format_exc())
            return 1

    # ------------------------------------------------------------------
    # DB persistence helpers
    # ------------------------------------------------------------------

    def _persist_account(self, email: str) -> None:
        """Insert or update the account in gmail_accounts."""
        from taktik.core.database.repositories.gmail import GmailAccountRepository
        if not GmailAccountRepository().upsert(email, self.device_id):
            send_log("warning", f"⚠️ Could not persist Gmail account {email}")

    def _unpersist_account(self, email: str) -> None:
        """Delete the account from gmail_accounts."""
        from taktik.core.database.repositories.gmail import GmailAccountRepository
        if not GmailAccountRepository().delete(email):
            send_log("warning", f"⚠️ Could not unpersist Gmail account {email}")


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"type": "error", "message": "Usage: gmail_account_bridge.py <config_path>"}))
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        send_error(f"Failed to load config: {e}")
        sys.exit(1)

    bridge = GmailAccountBridge(config)
    sys.exit(bridge.run())


if __name__ == '__main__':
    main()
