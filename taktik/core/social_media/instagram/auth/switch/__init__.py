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

import html
import re
import time
from typing import Callable, List, Optional

from loguru import logger

from ...ui.selectors.shell.auth import AUTH_SELECTORS
from .models import SwitchResult
from ..logout import InstagramLogout

# Profile-header stats leak into the dump behind the switcher sheet as content-desc like
# "36followers" / "1posts" / "91following". A username never has this "<digits><stat-word>" shape,
# so we drop them from the account enumeration.
_STAT_RE = re.compile(
    r"^\d+\s*(posts?|followers?|following|abonn\w*|abonn[ée]s?|publications?|mentions?|reels?|tagged)$",
    re.IGNORECASE,
)


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

    def _dump_xml(self) -> str:
        """Raw UI hierarchy XML. Tolerant to the device being a facade (`_device`/`device`)."""
        device = self.device
        for target in (device, getattr(device, "_device", None), getattr(device, "device", None)):
            fn = getattr(target, "dump_hierarchy", None) if target is not None else None
            if callable(fn):
                try:
                    return fn() or ""
                except Exception:
                    continue
        return ""

    def _clickable_labels(self) -> List[str]:
        """Every clickable node's content-desc on the current screen (raw, for enumeration +
        diagnostics). Parsed from the raw hierarchy XML — more reliable than xpath+attrib for
        the unlabelled ViewGroups (device-side: xpath returned nothing while the rows existed)."""
        xml = self._dump_xml()
        labels: List[str] = []
        for node in re.finditer(r"<node\b[^>]*>", xml):
            chunk = node.group(0)
            if 'clickable="true"' not in chunk:
                continue
            match = re.search(r'content-desc="([^"]*)"', chunk)
            if not match:
                continue
            desc = html.unescape(match.group(1)).strip()
            if desc:
                labels.append(desc)
        return labels

    def _list_accounts_on_screen(self) -> List[str]:
        """The connected-account usernames among the clickable rows (switcher sheet / picker).

        Each row's content-desc is the username (sometimes suffixed with ",  New notifications").
        Non-account buttons and the profile stats that leak behind the sheet are filtered out.
        """
        exclude = {label.lower() for label in self.auth.account_row_exclude_labels}
        found: List[str] = []
        seen = set()
        for desc in self._clickable_labels():
            # Drop a trailing ",  New notifications" / ", Nouvelles notifications".
            name = desc.split(",")[0].strip()
            low = name.lower()
            if not name or low in exclude or low in seen:
                continue
            # A username has no spaces (handles use letters/digits/._ only) and is never a
            # profile stat ("36followers") or a story label ("x's story").
            if " " in name or "'s story" in low or _STAT_RE.match(name):
                continue
            seen.add(low)
            found.append(name)
        return found

    def _switcher_is_open(self) -> bool:
        """The account switcher sheet / picker is open (shows the "Use another profile" button)."""
        return self._element_exists(self.auth.account_picker_indicators)

    def _open_account_switcher(self) -> bool:
        """Open the account switcher WITHOUT logging out: tap the @username (+ chevron) at the top
        of the Profile page. Returns True once the sheet (or its rows) is visible."""
        if self._switcher_is_open():
            return True
        # Wait for the profile header (the @username button) to be ready — after a cold IG restart
        # the profile can still be loading when we arrive.
        button = None
        for _ in range(10):
            if self._switcher_is_open():
                return True
            button = self._find_element(self.auth.profile_username_switcher_button)
            if button is not None:
                break
            time.sleep(0.5)
        if button is None:
            self.logger.warning("account switcher: profile @username button not found")
            return False
        # Tap the @username and wait for the sheet; retry once (the tap sometimes doesn't register
        # right after a cold start).
        for attempt in range(2):
            try:
                button.click()
                self.logger.info(f"account switcher: tapped profile @username (attempt {attempt + 1})")
            except Exception as exc:
                self.logger.warning(f"account switcher: tap failed: {exc}")
            time.sleep(1.5)
            for _ in range(6):
                if self._switcher_is_open() or self._list_accounts_on_screen():
                    self.logger.info("account switcher: opened")
                    return True
                time.sleep(0.5)
            button = self._find_element(self.auth.profile_username_switcher_button) or button
        self.logger.warning("account switcher: sheet not detected after tap")
        return self._switcher_is_open()

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

        # 0. Profile tab
        if not self._logout._open_profile_tab():
            return SwitchResult(False, "Profile tab not found", "profile_tab_not_found")

        # 1. DIRECT switch via the account switcher (NO logout): tap the @username at the top of
        # the profile, then the target row. The clean, fast path when it's available.
        detected: List[str] = []
        if self._open_account_switcher():
            detected = self._list_accounts_on_screen()
            self.logger.info(f"📋 Switcher accounts: {detected}")
            self._notify(f"{len(detected)} account(s) on this device")
            if any(self._norm(a) == target for a in detected):
                self._notify(f"Switching directly to @{target}…")
                if self._select_account(target):
                    time.sleep(3)
                    if self._logged_in_now():
                        self.logger.success(f"✅ Switched to @{target} (direct)")
                        return SwitchResult(True, f"Switched to @{target}", switched_to=target,
                                            detected_accounts=detected)
                    if self._password_required():
                        return SwitchResult(True, f"@{target} needs re-login (session not saved)",
                                            switched_to=target, relogin_required=True,
                                            detected_accounts=detected)
            # Target absent or tap inconclusive → close the sheet and use the logout fallback.
            try:
                self.device.press("back")
            except Exception:
                pass
            time.sleep(1)

        # 2. LOG OUT fallback — open the options menu, then reuse the logout navigation + dialogs.
        if not self._logout._open_options_menu():
            return SwitchResult(False, "Options menu not found", "options_menu_not_found",
                                detected_accounts=detected)
        self._notify("Logging out of the current account…")
        if not self._logout._find_and_click_logout():
            return SwitchResult(False, "Log out button not found", "logout_button_not_found",
                                detected_accounts=detected)
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

    def list_accounts(self) -> List[str]:
        """List the Instagram accounts logged in on the device, WITHOUT logging out.

        Opens the account switcher (profile @username → sheet) and enumerates the rows.
        Best-effort: returns [] if the switcher can't be opened.
        """
        self.logger.info("📋 Listing connected accounts")
        self._notify("Reading connected accounts…")
        if not self._logout._open_profile_tab():
            self._notify("Could not open the profile tab")
            return []
        opened = self._open_account_switcher()
        # Diagnostics visible in the FRONT log: is the switcher open, and what's on screen?
        labels = self._clickable_labels()
        self.logger.info(f"list_accounts: switcher_open={opened}, screen labels={labels[:20]}")
        self._notify(f"Switcher open: {opened} — screen: {labels[:10]}")
        accounts = self._list_accounts_on_screen()
        self.logger.info(f"📋 {len(accounts)} connected account(s): {accounts}")
        self._notify(f"Detected {len(accounts)} account(s): {accounts}")
        # Leave the UI clean (close the switcher sheet).
        try:
            self.device.press("back")
        except Exception:
            pass
        return accounts

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
