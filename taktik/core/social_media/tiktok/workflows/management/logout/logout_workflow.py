"""
TikTok Logout Workflow

Flow observé (app en anglais, dumps 02/05/2026) :
  1. Onglet Profile (barre de nav du bas)
  2. Bouton burger ≡ (Profile menu)
  3. "Settings and privacy"
  4. Scroll jusqu'en bas → "Log out"
  5. Popup de confirmation → "Log out" (rouge)
"""
import time
from loguru import logger
from bridges.common.ipc import IPC
from taktik.core.social_media.tiktok.ui.selectors.auth import LOGOUT_SELECTORS

_ipc = IPC()


class TikTokLogoutWorkflow:
    """Workflow for logging out of TikTok on a connected Android device."""

    def __init__(self, device, device_id: str):
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(device=device_id)

    # ------------------------------------------------------------------
    # Public entry-point
    # ------------------------------------------------------------------

    def execute(self) -> dict:
        """
        Execute the TikTok logout workflow.

        Returns:
            dict with keys: success (bool), message (str), error_type (str|None)
        """
        self.logger.info("🚪 TikTok logout workflow")

        try:
            _ipc.status("running", "Navigating to profile...")

            # ── Step 1 : Navigate to Profile tab ────────────────────────
            _ipc.log("info", "👤 Step 1 – Tapping Profile tab...")
            if not self._click_selector(LOGOUT_SELECTORS.profile_tab, timeout=6.0):
                return self._error("profile_tab_not_found",
                                   "Could not find Profile tab in bottom navigation")
            time.sleep(1.5)

            # ── Step 2 : Open Profile menu (burger ≡) ───────────────────
            _ipc.log("info", "☰ Step 2 – Opening profile menu...")
            if not self._click_selector(LOGOUT_SELECTORS.profile_menu_button, timeout=6.0):
                return self._error("profile_menu_not_found",
                                   "Could not find Profile menu button (≡)")
            time.sleep(1.0)

            # ── Step 3 : Tap "Settings and privacy" ─────────────────────
            _ipc.log("info", "⚙️  Step 3 – Tapping Settings and privacy...")
            if not self._click_selector(LOGOUT_SELECTORS.settings_and_privacy, timeout=6.0):
                return self._error("settings_not_found",
                                   "Could not find 'Settings and privacy'")
            time.sleep(1.5)

            # ── Step 4 : Scroll to "Log out" and tap it ──────────────────
            _ipc.log("info", "🔽 Step 4 – Scrolling to 'Log out' button...")
            if not self._scroll_to_and_click_logout():
                return self._error("logout_button_not_found",
                                   "Could not find 'Log out' button after scrolling")
            time.sleep(1.0)

            # ── Step 5 : Confirm logout in the bottom sheet popup ────────
            _ipc.log("info", "✅ Step 5 – Confirming logout...")
            if not self._confirm_logout():
                return self._error("logout_confirm_failed",
                                   "Could not confirm logout in the popup")

            _ipc.log("info", "✅ TikTok logout successful")
            _ipc.status("done", "Logged out successfully")
            return {"success": True, "message": "Logged out successfully", "error_type": None}

        except Exception as exc:
            self.logger.exception("💥 TikTok logout failed")
            _ipc.log("error", f"❌ Logout error: {exc}")
            return {"success": False, "message": str(exc), "error_type": "exception"}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
        _ipc.log("error", f"❌ {message}")
        return {"success": False, "message": message, "error_type": error_type}

    def _scroll_to_and_click_logout(self, max_swipes: int = 8) -> bool:
        """
        Scroll down the Settings and privacy page until the 'Log out' row is
        visible, then click it.

        The page is long (Activity center → ... → Log out at the very bottom),
        so we swipe upward (finger up = content moves up = reveals lower items)
        up to `max_swipes` times.
        """
        # Check first without scrolling (in case the page is already at the bottom)
        el = self._find_element(LOGOUT_SELECTORS.logout_button, timeout=2.0)
        if el:
            el.click()
            return True

        w, h = self.device.window_size()
        start_y = int(h * 0.70)
        end_y   = int(h * 0.30)

        for _ in range(max_swipes):
            self.device.swipe(w // 2, start_y, w // 2, end_y, duration=0.35)
            time.sleep(0.5)
            el = self._find_element(LOGOUT_SELECTORS.logout_button, timeout=1.5)
            if el:
                el.click()
                return True

        return False

    def _confirm_logout(self) -> bool:
        """
        Wait for the confirmation bottom sheet ("Are you sure you want to log out?")
        and tap the red "Log out" button to confirm.

        The confirm button in the popup has content-desc="Log out", which is
        distinct from the settings list item that only has text="Log out".
        """
        # Wait for the bottom sheet to appear
        sheet = self._find_element(LOGOUT_SELECTORS.logout_confirm_sheet, timeout=5.0)
        if not sheet:
            self.logger.warning("Logout confirmation sheet not detected — attempting to confirm anyway")

        return self._click_selector(LOGOUT_SELECTORS.logout_confirm_button, timeout=5.0)
