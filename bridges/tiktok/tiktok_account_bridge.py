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

from bridges.tiktok.base import (
    logger, _ipc,
    send_message, send_status, send_error, send_log,
)
from bridges.common.connection import ConnectionService
from bridges.common.app_manager import AppService
from bridges.common.signal_handler import setup_signal_handlers


class TikTokAccountBridge:
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

        # Boot TikTok
        send_status("initializing", "Launching TikTok...")
        app_service = AppService(self._connection, platform="tiktok",
                                  package_override=self.package_name)
        app_service.launch()

        # The app_service may have auto-selected an alternative package
        # (e.g. com.ss.android.ugc.trill when com.zhiliaoapp.musically is absent).
        # Patch all TikTok selector singletons so that resource-id references
        # (com.zhiliaoapp.musically:id/…) get rewritten to the actual package name.
        resolved_package = app_service.package
        if resolved_package != "com.zhiliaoapp.musically":
            try:
                from taktik.core.clone import set_active_package, patch_selectors_for_package
                set_active_package(resolved_package)
                patched = patch_selectors_for_package("tiktok", resolved_package)
                send_log("info", f"🧬 Package override: patched {patched} TikTok selector(s) for {resolved_package}")
            except Exception as e:
                send_log("warning", f"⚠️ Clone selector patching failed (non-fatal): {e}")

        import time
        time.sleep(2)

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

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def _run_login(self, device) -> int:
        username = self.config.get('username', '')
        password = self.config.get('password', '')
        save_session = self.config.get('saveSession', True)
        max_retries = self.config.get('maxRetries', 3)

        if not username or not password:
            send_error("username and password are required for login")
            return 1

        send_status("running", f"Starting login for @{username}...")
        send_log("info", f"🔐 Login workflow — @{username}")

        try:
            from taktik.core.social_media.tiktok.workflows.management.login.login_workflow import TikTokLoginWorkflow
            workflow = TikTokLoginWorkflow(device, self.device_id)
            result = workflow.execute(
                username=username,
                password=password,
                max_retries=max_retries,
                save_session=save_session,
            )
            outcome = "success" if result['success'] else "error"
            send_status(outcome, result.get('message', ''))
            send_message("account_result",
                         success=result['success'],
                         workflow="login",
                         username=username,
                         message=result.get('message', ''),
                         error_type=result.get('error_type'))
            return 0 if result['success'] else 1
        except Exception as e:
            import traceback
            send_error(f"Login error: {e}")
            send_log("error", traceback.format_exc())
            return 1

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    def _run_logout(self, device) -> int:
        send_status("running", "Starting logout...")
        send_log("info", "🚪 Logout workflow")

        try:
            from taktik.core.social_media.tiktok.workflows.management.logout.logout_workflow import TikTokLogoutWorkflow
            workflow = TikTokLogoutWorkflow(device, self.device_id)
            result = workflow.execute()
            outcome = "success" if result['success'] else "error"
            send_status(outcome, result.get('message', ''))
            send_message("account_result",
                         success=result['success'],
                         workflow="logout",
                         message=result.get('message', ''),
                         error_type=result.get('error_type'))
            return 0 if result['success'] else 1
        except Exception as e:
            import traceback
            send_error(f"Logout error: {e}")
            send_log("error", traceback.format_exc())
            return 1

    # ------------------------------------------------------------------
    # Register
    # ------------------------------------------------------------------

    def _run_register(self, device) -> int:
        method = self.config.get('method', 'email')  # "email" | "phone"
        email = self.config.get('email', '')
        phone = self.config.get('phone', '')
        phone_country = self.config.get('phoneCountry', '') or None
        gmail_password = self.config.get('gmailPassword', '') or None
        tiktok_password = self.config.get('tiktokPassword') or self.config.get('tiktok_password') or None
        nickname = self.config.get('nickname') or None

        send_status("running", f"Starting register ({method})...")
        send_log("info", f"📝 Register workflow — method={method}")

        try:
            from taktik.core.social_media.tiktok.workflows.management.signup.signup_workflow import TikTokSignupWorkflow
            workflow = TikTokSignupWorkflow(device, self.device_id)
            result = workflow.execute(
                method=method,
                email=email or None,
                phone=phone or None,
                phone_country=phone_country,
                gmail_password=gmail_password,
                tiktok_password=tiktok_password,
                nickname=nickname,
            )
            outcome = "success" if result['success'] else "error"
            send_status(outcome, result.get('message', ''))
            send_message("account_result",
                         success=result['success'],
                         workflow="register",
                         step=result.get('step', 'unknown'),
                         message=result.get('message', ''),
                         error_type=result.get('error_type'))
            return 0 if result['success'] else 1
        except Exception as e:
            import traceback
            send_error(f"Register error: {e}")
            send_log("error", traceback.format_exc())
            return 1


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"type": "error", "message": "Usage: tiktok_account_bridge.py <config_path>"}))
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        send_error(f"Failed to load config: {e}")
        sys.exit(1)

    bridge = TikTokAccountBridge(config)
    sys.exit(bridge.run())


if __name__ == '__main__':
    main()
