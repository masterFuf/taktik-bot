"""
TikTok Logout Workflow

Observed flow (English app, dumps 2026-05-02):
  1. Profile tab (bottom navigation)
  2. Burger menu
  3. "Settings and privacy"
  4. Scroll to bottom -> "Log out"
  5. Confirmation popup -> "Log out"
"""

import time
from contextvars import ContextVar

from loguru import logger

from taktik.core.social_media.tiktok.ui.selectors.shell.auth import LOGOUT_SELECTORS


class _NullNotifier:
    def status(self, *args, **kwargs):
        return None

    def log(self, *args, **kwargs):
        return None


_NULL_NOTIFIER = _NullNotifier()
_CURRENT_NOTIFIER: ContextVar = ContextVar("tiktok_logout_notifier", default=_NULL_NOTIFIER)


class _NotifierProxy:
    def __getattr__(self, name):
        return getattr(_CURRENT_NOTIFIER.get(), name)


_ipc = _NotifierProxy()


class TikTokLogoutWorkflow:
    """Workflow for logging out of TikTok on a connected Android device."""

    def __init__(self, device, device_id: str, notifier=None):
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(device=device_id)
        self._notifier = notifier or _NULL_NOTIFIER

    def execute(self) -> dict:
        """
        Execute the TikTok logout workflow.

        Returns:
            dict with keys: success (bool), message (str), error_type (str|None)
        """
        self.logger.info("TikTok logout workflow")
        token = _CURRENT_NOTIFIER.set(self._notifier)

        try:
            _ipc.status("running", "Navigating to profile...")

            _ipc.log("info", "Step 1 - Tapping Profile tab...")
            if not self._click_selector(LOGOUT_SELECTORS.profile_tab, timeout=6.0):
                return self._error("profile_tab_not_found", "Could not find Profile tab in bottom navigation")
            time.sleep(1.5)

            _ipc.log("info", "Step 2 - Opening profile menu...")
            if not self._click_selector(LOGOUT_SELECTORS.profile_menu_button, timeout=6.0):
                return self._error("profile_menu_not_found", "Could not find Profile menu button")
            time.sleep(1.0)

            _ipc.log("info", "Step 3 - Tapping Settings and privacy...")
            if not self._click_selector(LOGOUT_SELECTORS.settings_and_privacy, timeout=6.0):
                return self._error("settings_not_found", "Could not find 'Settings and privacy'")
            time.sleep(1.5)

            _ipc.log("info", "Step 4 - Scrolling to 'Log out' button...")
            if not self._scroll_to_and_click_logout():
                return self._error("logout_button_not_found", "Could not find 'Log out' button after scrolling")
            time.sleep(1.0)

            _ipc.log("info", "Step 5 - Confirming logout...")
            if not self._confirm_logout():
                return self._error("logout_confirm_failed", "Could not confirm logout in the popup")

            _ipc.log("info", "TikTok logout successful")
            _ipc.status("done", "Logged out successfully")
            return {"success": True, "message": "Logged out successfully", "error_type": None}

        except Exception as exc:
            self.logger.exception("TikTok logout failed")
            _ipc.log("error", f"Logout error: {exc}")
            return {"success": False, "message": str(exc), "error_type": "exception"}
        finally:
            _CURRENT_NOTIFIER.reset(token)

    def _find_element(self, selectors: list, timeout: float = 5.0):
        """Try each XPath selector and return the first matching element."""
        for xpath in selectors:
            try:
                el = self.device.xpath(xpath)
                if el.wait(timeout=timeout):
                    return el
            except Exception:
                continue
        return None

    def _click_selector(self, selectors: list, timeout: float = 5.0) -> bool:
        el = self._find_element(selectors, timeout)
        if el:
            el.click()
            return True
        return False

    def _error(self, error_type: str, message: str) -> dict:
        _ipc.log("error", message)
        return {"success": False, "message": message, "error_type": error_type}

    def _scroll_to_and_click_logout(self, max_swipes: int = 8) -> bool:
        """Scroll to the logout button and tap it."""
        el = self._find_element(LOGOUT_SELECTORS.logout_button, timeout=2.0)
        if el:
            el.click()
            return True

        w, h = self.device.window_size()
        start_y = int(h * 0.70)
        end_y = int(h * 0.30)

        for _ in range(max_swipes):
            self.device.swipe(w // 2, start_y, w // 2, end_y, duration=0.35)
            time.sleep(0.5)
            el = self._find_element(LOGOUT_SELECTORS.logout_button, timeout=1.5)
            if el:
                el.click()
                return True

        return False

    def _confirm_logout(self) -> bool:
        """Wait for the confirmation popup and tap the confirm button."""
        sheet = self._find_element(LOGOUT_SELECTORS.logout_confirm_sheet, timeout=5.0)
        if not sheet:
            self.logger.warning("Logout confirmation sheet not detected - attempting to confirm anyway")

        return self._click_selector(LOGOUT_SELECTORS.logout_confirm_button, timeout=5.0)
