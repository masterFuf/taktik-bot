"""YouTube account management workflow.

YouTube account login is mostly a Google-account/device concern: ensure the
Google account exists on Android, open YouTube, then switch to that identity if
the account picker is automatable.
"""

from __future__ import annotations

import time
import traceback
from typing import Any, Callable, Protocol

from loguru import logger

from taktik.core.social_media.youtube.ui.selectors.account import (
    ACCOUNT_SELECTORS,
    YOUTUBE_HOME_ACTIVITY,
)
from taktik.core.social_media.youtube.ui.selectors.upload import YOUTUBE_PACKAGE


class AccountRepository(Protocol):
    def upsert(self, email: str, device_id: str) -> bool:
        """Persist a Google account identity for the current device."""


class GmailWorkflowFactory(Protocol):
    def __call__(self, device, device_id: str, notifier=None) -> Any:
        """Create the Gmail workflow used to ensure Android Google accounts."""


class YouTubeAccountWorkflow:
    """Core YouTube account flow, independent from bridge stdout plumbing."""

    def __init__(
        self,
        device,
        device_id: str,
        *,
        notifier=None,
        gmail_workflow_factory: GmailWorkflowFactory | None = None,
        account_repository: AccountRepository | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.device = device
        self.device_id = device_id
        self._notifier = notifier
        self._gmail_workflow_factory = gmail_workflow_factory
        self._account_repository = account_repository
        self._sleep = sleeper
        self.logger = logger.bind(device=device_id)

    def login(self, *, email: str, password: str = "") -> dict[str, Any]:
        """Ensure a Google account exists, then open YouTube on that account."""
        email = email.strip()
        password = password.strip()
        if not email:
            return self._failure("email is required for YouTube login", "validation")

        try:
            self._status("running", "Ensuring Google account is registered on device...")
            self._log("info", f"YouTube login - {email}")

            if password:
                self._ensure_gmail_account(email, password)
            else:
                self._log(
                    "info",
                    "No password provided - assuming account already registered on device",
                )

            self._status("running", "Checking YouTube is installed...")
            if not self._is_youtube_installed():
                return self._failure(
                    f"YouTube ({YOUTUBE_PACKAGE}) is not installed on this device. "
                    "Install it from the Play Store first.",
                    "app_not_installed",
                )

            self._status("running", "Opening YouTube...")
            if not self._launch_youtube():
                return self._failure("Failed to launch YouTube", "launch_failed")

            self._status("running", "Verifying YouTube is open...")
            if not self._wait_until_youtube_open():
                return self._failure(
                    "YouTube did not open. Check the device screen - the app may "
                    "not be installed or may require a manual tap.",
                    "launch_failed",
                )

            self._dismiss_popups()

            self._status("running", f"Switching to account {email} in YouTube...")
            if self._switch_youtube_account(email):
                self._log("info", f"Switched to {email} in YouTube")
            else:
                self._log(
                    "info",
                    "Account switch not automated - YouTube is open, switch manually if needed",
                )

            self._persist_account(email)
            return {
                "success": True,
                "workflow": "login",
                "email": email,
                "message": f"YouTube opened with account {email}",
            }
        except Exception as exc:  # noqa: BLE001 - workflow returns structured failures
            self._log("error", traceback.format_exc())
            return self._failure(str(exc), type(exc).__name__)

    def logout(self, *, email: str = "") -> dict[str, Any]:
        """Open Android account settings; actual removal remains user-confirmed."""
        email = email.strip()
        self._status("running", "Opening YouTube account settings...")
        self._log("info", f"YouTube logout - opening settings for {email or 'current account'}")
        try:
            self.device.shell("am start -a android.settings.ACCOUNT_SYNC_SETTINGS")
        except Exception as exc:  # noqa: BLE001 - opening settings is best effort
            self._log("warning", f"Could not open account settings: {exc}")

        return {
            "success": True,
            "workflow": "logout",
            "email": email,
            "message": "Manage your account in Android Settings",
        }

    def _ensure_gmail_account(self, email: str, password: str) -> None:
        self._log("info", "Password provided - will add account to Gmail if missing")
        try:
            factory = self._gmail_workflow_factory or _default_gmail_workflow_factory
            result = factory(self.device, self.device_id, notifier=self._notifier).ensure_account_added(
                email,
                password,
            )
        except Exception as exc:  # noqa: BLE001 - Android account may already exist
            self._log("warning", f"Could not run Gmail workflow: {exc}")
            self._log("debug", traceback.format_exc())
            return

        if not result.get("success"):
            self._log(
                "warning",
                f"Gmail ensure_account_added: {result.get('message', 'unknown')}",
            )
        else:
            self._log("info", f"Gmail account ensured: {email}")

    def _is_youtube_installed(self) -> bool:
        try:
            pkg_check = self.device.shell(f"pm list packages {YOUTUBE_PACKAGE}").strip()
        except Exception as exc:  # noqa: BLE001
            self._log("warning", f"Could not verify YouTube installation: {exc}")
            return True
        return YOUTUBE_PACKAGE in pkg_check

    def _launch_youtube(self) -> bool:
        try:
            launch_out = self.device.shell(
                f"monkey -p {YOUTUBE_PACKAGE} -c android.intent.category.LAUNCHER 1"
            ).strip()
            self._log("debug", f"Launch output: {launch_out}")
            if "error" not in launch_out.lower() and "events injected: 0" not in launch_out.lower():
                return True

            am_out = self.device.shell(f"am start -n {YOUTUBE_HOME_ACTIVITY}").strip()
            self._log("debug", f"am start output: {am_out}")
            return "error" not in am_out.lower()
        except Exception as exc:  # noqa: BLE001
            self._log("error", f"Failed to launch YouTube: {exc}")
            return False

    def _wait_until_youtube_open(self) -> bool:
        for attempt in range(6):
            self._sleep(1)
            try:
                current_app = self.device.shell("dumpsys window windows | grep mCurrentFocus").strip()
                self._log("debug", f"Current focus ({attempt + 1}): {current_app}")
                if YOUTUBE_PACKAGE in current_app:
                    self._log("info", "YouTube is in foreground")
                    return True
            except Exception:
                continue

        try:
            top = self.device.shell("dumpsys activity activities | grep mResumedActivity").strip()
            if YOUTUBE_PACKAGE in top:
                self._log("info", "YouTube is active (mResumedActivity)")
                return True
            self._log("warning", f"YouTube does not appear to be in foreground. Current: {top}")
        except Exception:
            pass
        return False

    def _dismiss_popups(self) -> None:
        for _round in range(3):
            dismissed = False
            for selector in ACCOUNT_SELECTORS.launch_popup_close:
                try:
                    element = _query_selector(self.device, selector.kind, selector.value)
                    if element.exists(timeout=1):
                        element.click()
                        self._log("info", f"Dismissed popup ({selector.kind}={selector.value!r})")
                        self._sleep(0.8)
                        dismissed = True
                        break
                except Exception:
                    continue
            if not dismissed:
                break

    def _switch_youtube_account(self, email: str) -> bool:
        try:
            self.device.dump_hierarchy(compressed=False)
            for query in ACCOUNT_SELECTORS.account_button_queries_for_email(email):
                try:
                    element = self.device(query)
                    if not element.exists(timeout=1.5):
                        continue
                    element.click()
                    self._sleep(1.5)
                    account_entry = ACCOUNT_SELECTORS.account_entry_for_email(email)
                    email_element = _query_selector(
                        self.device,
                        account_entry.kind,
                        account_entry.value,
                    )
                    if email_element.exists(timeout=2):
                        email_element.click()
                        self._sleep(1)
                        return True
                    break
                except Exception:
                    continue
        except Exception as exc:  # noqa: BLE001
            self.logger.debug(f"YouTube account switch attempt failed: {exc}")
        return False

    def _persist_account(self, email: str) -> None:
        repository = self._account_repository
        if repository is None:
            repository = _default_account_repository()
        if not repository.upsert(email, self.device_id):
            self._log("warning", f"Could not persist account {email}")

    def _status(self, status: str, message: str) -> None:
        if self._notifier is None:
            return
        callback = getattr(self._notifier, "status", None)
        if callback is not None:
            try:
                callback(status, message)
            except Exception:
                pass

    def _log(self, level: str, message: str) -> None:
        getattr(self.logger, level, self.logger.info)(message)
        if self._notifier is None:
            return
        callback = getattr(self._notifier, "log", None)
        if callback is not None:
            try:
                callback(level, message)
            except Exception:
                pass

    def _failure(self, message: str, error_type: str) -> dict[str, Any]:
        return {
            "success": False,
            "message": message,
            "error_type": error_type,
        }


def _query_selector(device, kind: str, value: str):
    if kind == "resourceId":
        return device(resourceId=value)
    if kind == "description":
        return device(description=value)
    return device(text=value)


def _default_gmail_workflow_factory(device, device_id: str, notifier=None):
    from taktik.core.app.email.gmail.workflows.account import GmailWorkflow

    return GmailWorkflow(device, device_id, notifier=notifier)


def _default_account_repository() -> AccountRepository:
    from taktik.core.database.repositories.gmail import GmailAccountRepository

    return GmailAccountRepository()
