"""
Logout process for Instagram.

Flow (from UI dumps):
1. Click Profile tab (bottom navigation)
2. Click "Options" hamburger (top-right of profile page)
3. Scroll down in Settings and activity menu
4. Click "Log out" button
5. Confirm in the dialog
"""

import time
from typing import Optional
from loguru import logger

from ...ui.selectors.shell.auth import AUTH_SELECTORS
from ...actions.atomic.interaction import ClickActions
from ...actions.atomic.detection import DetectionActions

from .models import LogoutResult


class InstagramLogout:
    """Gestionnaire de déconnexion Instagram."""

    def __init__(self, device, device_id: str):
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(module="instagram-logout")

        self.auth_selectors = AUTH_SELECTORS
        self.click_actions = ClickActions(device)
        self.detection_actions = DetectionActions(device)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _find_element(self, selectors: list):
        """Find first matching element from a list of xpath selectors."""
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    return element
            except Exception:
                continue
        return None

    def _click_first_match(self, selectors: list, element_name: str) -> bool:
        """Click first matching element from a list of xpath selectors."""
        element = self._find_element(selectors)
        if element:
            try:
                element.click()
                self.logger.success(f"✅ Clicked '{element_name}'")
                return True
            except Exception as exc:
                self.logger.error(f"❌ Click on '{element_name}' failed: {exc}")
        return False

    def _element_exists(self, selectors: list) -> bool:
        return self._find_element(selectors) is not None

    def _scroll_down(self, times: int = 1) -> None:
        """Scroll down in the current scrollable view."""
        try:
            width, height = self.device.window_size()
        except Exception:
            width, height = 720, 1280

        x = width // 2
        y_start = int(height * 0.75)
        y_end = int(height * 0.25)

        for _ in range(times):
            try:
                self.device.swipe(x, y_start, x, y_end, duration=0.4)
                time.sleep(0.6)
            except Exception as exc:
                self.logger.warning(f"⚠️ Swipe failed: {exc}")
                break

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------
    def _open_profile_tab(self) -> bool:
        self.logger.info("👤 Opening Profile tab...")
        if not self._click_first_match(self.auth_selectors.profile_tab_button, "Profile tab"):
            return False
        time.sleep(2)
        return True

    def _open_options_menu(self) -> bool:
        self.logger.info("⚙️ Opening Options menu...")
        if not self._click_first_match(self.auth_selectors.profile_options_button, "Options menu"):
            return False
        time.sleep(2)
        return True

    def _find_and_click_logout(self, max_scrolls: int = 8) -> bool:
        """Scroll until the Log out button is visible, then click it."""
        self.logger.info("🔎 Looking for 'Log out' button (scrolling)...")
        for attempt in range(max_scrolls + 1):
            if self._element_exists(self.auth_selectors.logout_button):
                if self._click_first_match(self.auth_selectors.logout_button, "Log out"):
                    return True
            if attempt < max_scrolls:
                self._scroll_down(1)
        self.logger.error("❌ 'Log out' button not found after scrolling")
        return False

    def _confirm_logout(self) -> bool:
        """
        Handle the two post-click dialogs:
          1. "Save your login info?" → click "Not now"
          2. "Log out of your account?" → click "Log out" (primary button)
        """
        # Give the first dialog time to appear
        time.sleep(1.5)

        # ── Dialog 1: "Save your login info?" ─────────────────────────────
        if self._element_exists(self.auth_selectors.save_login_info_dialog_indicators):
            self.logger.info("💾 'Save your login info?' dialog detected → clicking 'Not now'")
            self._click_first_match(
                self.auth_selectors.save_login_info_not_now_button,
                "Not now (save login)"
            )
            time.sleep(1.5)

        # ── Dialog 2: "Log out of your account?" ──────────────────────────
        if self._element_exists(self.auth_selectors.logout_confirm_dialog_indicators):
            self.logger.info("🗨️ 'Log out of your account?' dialog detected → confirming")
            self._click_first_match(
                self.auth_selectors.logout_confirm_button,
                "Log out (confirm)"
            )
            time.sleep(2)
            return True

        # Fallback: no dialog appeared, logout may have completed directly
        self.logger.info("ℹ️ No confirmation dialogs detected (logout may already be complete)")
        return True

    def _is_logged_out(self) -> bool:
        """Verify we returned to the login screen after logout."""
        # Login screen shows the username field
        try:
            return self._element_exists(self.auth_selectors.username_field)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def logout(self) -> LogoutResult:
        """Déconnecte l'utilisateur actuellement connecté."""
        self.logger.info("🚪 Starting logout process")

        if not self._open_profile_tab():
            return LogoutResult(
                success=False,
                message="Profile tab not found",
                error_type="profile_tab_not_found",
            )

        if not self._open_options_menu():
            return LogoutResult(
                success=False,
                message="Options menu not found on profile page",
                error_type="options_menu_not_found",
            )

        if not self._find_and_click_logout():
            return LogoutResult(
                success=False,
                message="Log out button not found in Settings menu",
                error_type="logout_button_not_found",
            )

        self._confirm_logout()

        # Give Instagram some time to return to the login screen
        time.sleep(3)

        if self._is_logged_out():
            self.logger.success("✅ Logout successful")
            return LogoutResult(success=True, message="Logout successful")

        # Even if we don't see the login screen, the logout click happened.
        self.logger.warning("⚠️ Logout clicked but login screen not detected")
        return LogoutResult(
            success=True,
            message="Logout click performed (login screen not confirmed)",
        )


__all__ = ["InstagramLogout", "LogoutResult"]
