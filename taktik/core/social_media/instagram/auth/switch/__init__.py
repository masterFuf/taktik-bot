"""
Switch between Instagram accounts already logged in on the device.

Flow (from UI dumps, 2026-07-01):
1. Open Profile tab → Options menu (reuses the logout navigation).
2. DIRECT attempt: if the connected-accounts list is shown in the menu, tap the
   target row right away (cheap opportunistic path; absent in the captured dumps).
3. Otherwise LOG OUT (the real path): Settings → Log out → confirm dialogs.
4. Reach the logged-out "picker" of connected accounts, handling the case where
   Instagram auto-switches to ANOTHER account's home feed instead (→ log out again).
5. Tap the target account row (content-desc = username, language-neutral).
6. If the target's session is saved → it logs straight in. If not → the password
   screen appears → report `relogin_required` so the front routes to Login.

The bot only switches between accounts ALREADY connected on the device; connecting
a brand-new account is the Login flow's job.
"""

import time
from typing import Callable, List, Optional

from loguru import logger

from ...ui.selectors.shell.auth import AUTH_SELECTORS
from .models import SwitchResult
from ..logout import InstagramLogout


class InstagramSwitchAccount:
    """Gestionnaire de changement de compte Instagram (comptes déjà connectés)."""

    MAX_LOGOUT_LOOPS = 3  # guards the auto-switch-to-home loop

    def __init__(self, device, device_id: str, notifier: Optional[Callable[[str], None]] = None):
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(module="instagram-switch-account")
        self.auth = AUTH_SELECTORS
        # Reuse the logout navigation (profile tab → options menu → log out → dialogs).
        self._logout = InstagramLogout(device, device_id)
        self._notify = notifier or (lambda _msg: None)

    # ------------------------------------------------------------------
    # Helpers (delegate the low-level find/click to the logout navigator)
    # ------------------------------------------------------------------
    def _find_element(self, selectors: list):
        return self._logout._find_element(selectors)

    def _element_exists(self, selectors: list) -> bool:
        return self._logout._element_exists(selectors)

    def _click_first_match(self, selectors: list, name: str) -> bool:
        return self._logout._click_first_match(selectors, name)

    @staticmethod
    def _norm(username: str) -> str:
        return (username or "").lstrip("@").strip().lower()

    def _on_home_feed(self) -> bool:
        return self._element_exists(self.auth.home_feed_indicators)

    def _on_account_picker(self) -> bool:
        return self._element_exists(self.auth.account_picker_indicators)

    def _password_required(self) -> bool:
        """The target account is connected but its session is not saved (password screen)."""
        return (
            self._element_exists(self.auth.password_only_screen_indicators)
            or self._element_exists(self.auth.login_screen_indicators)
        )

    def _list_accounts_on_screen(self) -> List[str]:
        """Enumerate the connected-account rows visible on screen (picker or menu).

        Each row is a clickable ViewGroup whose content-desc is the username (sometimes
        suffixed with ",  New notifications"). The non-account buttons are filtered out.
        """
        exclude = {label.lower() for label in self.auth.account_row_exclude_labels}
        found: List[str] = []
        seen = set()
        for selector in self.auth.account_row_candidates:
            try:
                elements = self.device.xpath(selector).all()
            except Exception:
                continue
            for element in elements:
                try:
                    desc = (element.attrib.get("content-desc", "") or "").strip()
                except Exception:
                    continue
                if not desc:
                    continue
                # Drop a trailing ",  New notifications" / ", Nouvelles notifications".
                name = desc.split(",")[0].strip()
                low = name.lower()
                if not name or low in exclude or low in seen:
                    continue
                # A username has no spaces (handles use letters/digits/._ only).
                if " " in name:
                    continue
                seen.add(low)
                found.append(name)
        return found

    def _select_account(self, target: str) -> bool:
        clean = target.lstrip("@")
        for selector in self.auth.saved_profile_tile_selectors(target, clean):
            if self._click_first_match([selector], f"account @{clean}"):
                return True
        return False

    def _logged_in_now(self) -> bool:
        """We are logged in (home feed) and NOT on the picker → the switch landed."""
        return self._on_home_feed() and not self._on_account_picker()

    def _reach_login_navigation(self) -> bool:
        return self._logout._open_profile_tab() and self._logout._open_options_menu()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def switch_to(self, target_username: str) -> SwitchResult:
        target = self._norm(target_username)
        if not target:
            return SwitchResult(False, "No target username", "no_target")

        self.logger.info(f"🔀 Switching to @{target}")
        self._notify(f"Switching to @{target}")

        # 0. Profile tab → Options menu
        if not self._logout._open_profile_tab():
            return SwitchResult(False, "Profile tab not found", "profile_tab_not_found")
        if not self._logout._open_options_menu():
            return SwitchResult(False, "Options menu not found", "options_menu_not_found")

        # 1. DIRECT attempt: some IG versions list the connected accounts in the menu.
        menu_accounts = self._list_accounts_on_screen()
        if any(self._norm(a) == target for a in menu_accounts):
            self.logger.info("➡️ Account list present in menu, trying a direct switch")
            self._notify("Account list in menu, switching directly…")
            if self._select_account(target):
                time.sleep(3)
                if self._logged_in_now():
                    return SwitchResult(True, f"Switched to @{target}", switched_to=target,
                                        detected_accounts=menu_accounts)
                if self._password_required():
                    return SwitchResult(True, f"@{target} needs re-login (session not saved)",
                                        switched_to=target, relogin_required=True,
                                        detected_accounts=menu_accounts)
            # direct attempt inconclusive → fall through to the logout path

        # 2. LOG OUT (the real path) — reuse the logout navigation + dialogs.
        self._notify("Logging out of the current account…")
        if not self._logout._find_and_click_logout():
            return SwitchResult(False, "Log out button not found", "logout_button_not_found",
                                detected_accounts=menu_accounts)
        self._logout._confirm_logout()
        time.sleep(3)

        # 3. Reach the account picker, handling Instagram auto-switching to another home feed.
        if not self._ensure_on_picker():
            return SwitchResult(False, "Account picker not reached", "picker_unreachable")

        # 4. Enumerate + select the target on the picker.
        picker_accounts = self._list_accounts_on_screen()
        self.logger.info(f"📋 {len(picker_accounts)} connected account(s): {picker_accounts}")
        self._notify(f"{len(picker_accounts)} account(s) connected on this device")
        if not any(self._norm(a) == target for a in picker_accounts):
            return SwitchResult(False, f"@{target} is not connected on this device",
                                "target_not_connected", detected_accounts=picker_accounts)
        self._notify(f"Selecting @{target}…")
        if not self._select_account(target):
            return SwitchResult(False, f"Could not tap @{target}", "select_failed",
                                detected_accounts=picker_accounts)
        time.sleep(3)

        # 5. Either it logged straight in, or the password screen appeared (session not saved).
        if self._password_required():
            self.logger.warning(f"🔐 @{target} requires re-login (session not saved)")
            return SwitchResult(True, f"@{target} requires re-login (session not saved)",
                                switched_to=target, relogin_required=True,
                                detected_accounts=picker_accounts)

        self.logger.success(f"✅ Switched to @{target}")
        return SwitchResult(True, f"Switched to @{target}", switched_to=target,
                            detected_accounts=picker_accounts)

    def _ensure_on_picker(self) -> bool:
        """After logout, make sure we land on the account picker.

        If Instagram auto-switched to another connected account's HOME feed instead, log out
        again to come back to the picker (bounded by MAX_LOGOUT_LOOPS).
        """
        for _ in range(self.MAX_LOGOUT_LOOPS):
            if self._on_account_picker():
                return True
            if self._on_home_feed():
                self.logger.info("🏠 Auto-switched to another account's home → logging out again")
                self._notify("Instagram switched to another account, logging out again…")
                if not (self._reach_login_navigation() and self._logout._find_and_click_logout()):
                    return self._on_account_picker()
                self._logout._confirm_logout()
                time.sleep(3)
                continue
            # Transitional screen → give it a moment.
            time.sleep(1.5)
        return self._on_account_picker()


__all__ = ["InstagramSwitchAccount", "SwitchResult"]
