#!/usr/bin/env python3
"""
YouTube Account Bridge

Handles:
  - workflowType: "login"   → ensure the Google account is added to the device
                               via Gmail, then open YouTube and switch to it
  - workflowType: "logout"  → sign out from the YouTube account (opens settings)

Config JSON:
  {
    "workflowType": "login",
    "deviceId": "...",
    "email": "..."
  }

Strategy
--------
YouTube uses Google accounts that are already registered at the Android OS
level (managed by Gmail / Google Account Manager).  If the account is already
in Gmail the user can sign in to YouTube with a single tap.  This bridge:

  1. Calls GmailWorkflow.ensure_account_added() to guarantee the Google account
     is present on the device (it is a no-op if it is already there).
  2. Launches YouTube (com.google.android.youtube).
  3. Attempts to switch to the target account inside YouTube's account picker.
"""

import sys
import os
import json
import signal
import time

# Bootstrap: UTF-8 + loguru + sys.path
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)
from bridges.common.bootstrap import setup_environment
setup_environment()

from bridges.youtube.base import (
    logger, _ipc,
    send_message, send_status, send_error, send_log,
)
from bridges.common.connection import ConnectionService
from bridges.common.signal_handler import setup_signal_handlers

_YOUTUBE_PACKAGE = "com.google.android.youtube"
_YOUTUBE_ACTIVITY = "com.google.android.youtube/.app.honeycomb.Shell$HomeActivity"


class YouTubeAccountBridge:

    def __init__(self, config: dict):
        self.config = config
        self.device_id = config.get('deviceId')
        self.workflow_type = config.get('workflowType', 'login')
        self._connection = None

        setup_signal_handlers(ipc=_ipc)
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum, frame):
        send_status("stopping", "Received shutdown signal")

    # ──────────────────────────────────────────────────────────────────────────
    # Entrypoint
    # ──────────────────────────────────────────────────────────────────────────

    def run(self) -> int:
        if not self.device_id:
            send_error("deviceId is required")
            return 1

        try:
            from taktik.core.database import configure_db_service
            configure_db_service()
        except Exception as e:
            send_error(f"Database setup failed: {e}")
            return 1

        send_status("connecting", f"Connecting to device {self.device_id}…")
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
            elif self.workflow_type == "logout":
                return self._run_logout(device)
            else:
                send_error(f"Unknown workflowType: {self.workflow_type}")
                return 1
        finally:
            from bridges.common.app_manager import force_stop_app
            force_stop_app(self.device_id, "youtube")

    # ──────────────────────────────────────────────────────────────────────────
    # Login
    # ──────────────────────────────────────────────────────────────────────────

    def _run_login(self, device) -> int:
        email = (self.config.get('email') or '').strip()
        if not email:
            send_error("email is required for YouTube login")
            return 1

        # ── Step 1: ensure Google account is in Gmail ───────────────────────
        send_status("running", f"Ensuring Google account is registered on device…")
        send_log("info", f"▶️  YouTube login — {email}")

        password = (self.config.get('password') or '').strip()
        if password:
            send_log("info", "🔑 Password provided — will add account to Gmail if missing")
            try:
                from taktik.core.app.email.gmail.workflows.account import GmailWorkflow
                gw = GmailWorkflow(device, self.device_id, notifier=_ipc)
                result = gw.ensure_account_added(email, password)
                if not result.get('success'):
                    # Non-fatal: account might already be registered via Android Settings
                    send_log("warning", f"⚠️  Gmail ensure_account_added: {result.get('message', 'unknown')}")
                else:
                    send_log("info", f"✅ Gmail account ensured: {email}")
            except Exception as e:
                import traceback
                send_log("warning", f"⚠️  Could not run Gmail workflow: {e}")
                send_log("debug", traceback.format_exc())
        else:
            send_log("info", "ℹ️  No password provided — assuming account already registered on device")

        # ── Step 2: check YouTube is installed ──────────────────────────────
        send_status("running", "Checking YouTube is installed…")
        try:
            pkg_check = device.shell(f"pm list packages {_YOUTUBE_PACKAGE}").strip()
            if _YOUTUBE_PACKAGE not in pkg_check:
                send_error(f"YouTube ({_YOUTUBE_PACKAGE}) is not installed on this device. Install it from the Play Store first.")
                return 1
            send_log("info", f"✅ YouTube is installed")
        except Exception as e:
            send_log("warning", f"⚠️  Could not verify YouTube installation: {e}")

        # ── Step 3: launch YouTube ───────────────────────────────────────────
        send_status("running", "Opening YouTube…")
        send_log("info", f"📺 Launching YouTube ({_YOUTUBE_PACKAGE})")
        try:
            # Use the launcher intent — more reliable than hardcoding the activity name
            launch_out = device.shell(
                f"monkey -p {_YOUTUBE_PACKAGE} -c android.intent.category.LAUNCHER 1"
            ).strip()
            send_log("debug", f"Launch output: {launch_out}")
            if "error" in launch_out.lower() or "events injected: 0" in launch_out.lower():
                # Fallback: explicit activity
                am_out = device.shell(f"am start -n {_YOUTUBE_ACTIVITY}").strip()
                send_log("debug", f"am start output: {am_out}")
                if "error" in am_out.lower():
                    send_error(f"Failed to launch YouTube: {am_out}")
                    return 1
        except Exception as e:
            send_error(f"Failed to launch YouTube: {e}")
            return 1

        # ── Step 4: wait and verify YouTube is in foreground ─────────────────
        send_status("running", "Verifying YouTube is open…")
        youtube_open = False
        for attempt in range(6):  # up to 6 seconds
            time.sleep(1)
            try:
                current_app = device.shell("dumpsys window windows | grep mCurrentFocus").strip()
                send_log("debug", f"Current focus ({attempt+1}): {current_app}")
                if _YOUTUBE_PACKAGE in current_app:
                    youtube_open = True
                    send_log("info", f"✅ YouTube is in foreground")
                    break
            except Exception:
                pass

        if not youtube_open:
            # Last resort: check top activity
            try:
                top = device.shell("dumpsys activity activities | grep mResumedActivity").strip()
                if _YOUTUBE_PACKAGE in top:
                    youtube_open = True
                    send_log("info", f"✅ YouTube is active (mResumedActivity)")
                else:
                    send_log("warning", f"⚠️  YouTube does not appear to be in foreground. Current: {top}")
            except Exception:
                pass

        if not youtube_open:
            send_error("YouTube did not open. Check the device screen — the app may not be installed or may require a manual tap.")
            return 1

        # ── Step 5.5: dismiss interstitial popups (Premium, etc.) ───────────
        self._dismiss_popups(device)

        # ── Step 5: try to switch account inside YouTube ────────────────────
        send_status("running", f"Switching to account {email} in YouTube…")
        switched = self._switch_youtube_account(device, email)
        if switched:
            send_log("info", f"✅ Switched to {email} in YouTube")
        else:
            send_log("info", "ℹ️  Account switch not automated — YouTube is open, switch manually if needed")

        # ── Persist ─────────────────────────────────────────────────────────
        self._persist_account(email)

        send_status("success", f"YouTube ready with account {email}")
        send_message("account_result",
                     success=True,
                     workflow="login",
                     email=email,
                     message=f"YouTube opened with account {email}")
        return 0

    def _dismiss_popups(self, device) -> None:
        """
        Dismiss common YouTube interstitial popups that appear after launch:
        - YouTube Premium upsell
        - "What's new" dialogs
        - Cookie/consent screens
        Tries up to 3 rounds so chained popups are all cleared.
        """
        close_selectors = [
            # Notification permission popup (system) — deny it
            {'resourceId': 'com.android.permissioncontroller:id/permission_deny_button'},
            # In-app YouTube notification dialog ("Activer les notifications" / "Enable notifications") — cancel
            {'resourceId': f'{_YOUTUBE_PACKAGE}:id/custom_confirm_dialog_cancel_button'},
            # Premium popup close button (X in top-right)
            {'resourceId': f'{_YOUTUBE_PACKAGE}:id/close_button'},
            {'resourceId': f'{_YOUTUBE_PACKAGE}:id/dismiss_button'},
            {'resourceId': f'{_YOUTUBE_PACKAGE}:id/cancel_button'},
            {'description': 'Close'},
            {'description': 'Dismiss'},
            {'description': 'Not now'},
            {'text': 'No thanks'},
            {'text': 'Non merci'},
            {'text': 'Not now'},
            {'text': 'Skip'},
            {'text': 'Cancel'},
            {'text': 'Close'},
            {'text': 'Ne pas autoriser'},
            {"text": "Don't allow"},
        ]
        for _round in range(3):
            dismissed = False
            for sel in close_selectors:
                try:
                    key, val = list(sel.items())[0]
                    if key == 'resourceId':
                        el = device(resourceId=val)
                    elif key == 'description':
                        el = device(description=val)
                    else:
                        el = device(text=val)
                    if el.exists(timeout=1):
                        el.click()
                        send_log("info", f"✅ Dismissed popup ({key}={val!r})")
                        time.sleep(0.8)
                        dismissed = True
                        break
                except Exception:
                    continue
            if not dismissed:
                break  # No more popups

    def _switch_youtube_account(self, device, email: str) -> bool:
        """
        Attempt to switch YouTube to the target account via the account picker.
        Returns True if we confirmed the switch, False if we couldn't automate it.
        """
        try:
            # Look for an account avatar / profile button (top-right area)
            hierarchy = device.dump_hierarchy(compressed=False)

            # Try to tap the profile/account button (content-desc contains "Account" or the email)
            selectors = [
                f'[content-desc*="{email}"]',
                '[content-desc*="Account"]',
                '[content-desc*="Compte"]',
                f'[resource-id="{_YOUTUBE_PACKAGE}:id/account_icon_layout"]',
                f'[resource-id="{_YOUTUBE_PACKAGE}:id/avatar"]',
            ]
            for sel in selectors:
                try:
                    el = device(sel.lstrip('[').rstrip(']'))
                    if el.exists(timeout=1.5):
                        el.click()
                        time.sleep(1.5)
                        # Now look for the target email in the account list
                        email_el = device(text=email)
                        if email_el.exists(timeout=2):
                            email_el.click()
                            time.sleep(1)
                            return True
                        break
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"YouTube account switch attempt failed: {e}")
        return False

    # ──────────────────────────────────────────────────────────────────────────
    # Logout
    # ──────────────────────────────────────────────────────────────────────────

    def _run_logout(self, device) -> int:
        email = (self.config.get('email') or '').strip()
        send_status("running", "Opening YouTube account settings…")
        send_log("info", f"🚪 YouTube logout — opening settings for {email or 'current account'}")
        try:
            # Open Android account settings — user confirms removal manually
            device.shell("am start -a android.settings.ACCOUNT_SYNC_SETTINGS")
        except Exception:
            pass
        send_status("success", "YouTube account settings opened")
        send_message("account_result",
                     success=True,
                     workflow="logout",
                     email=email,
                     message="Manage your account in Android Settings")
        return 0

    # ──────────────────────────────────────────────────────────────────────────
    # DB helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _persist_account(self, email: str) -> None:
        """Reuse the gmail_accounts table — same Google account."""
        from taktik.core.database.repositories.gmail import GmailAccountRepository
        if not GmailAccountRepository().upsert(email, self.device_id):
            send_log("warning", f"⚠️ Could not persist account {email}")


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"type": "error", "message": "Usage: youtube_account_bridge.py <config_path>"}))
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        send_error(f"Failed to load config: {e}")
        sys.exit(1)

    bridge = YouTubeAccountBridge(config)
    sys.exit(bridge.run())


if __name__ == '__main__':
    main()
