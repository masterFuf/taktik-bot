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

from taktik.core.social_media.account_management import (
    AccountCatalog,
    is_account_username,
    normalize_account_username,
)

from ...ui.selectors.shell.auth import AUTH_SELECTORS
from ..logout import InstagramLogout
from .models import SwitchResult

# Profile-header stats leak into the dump behind the switcher sheet as content-desc like
# "36followers" / "1posts" / "91following". A username never has this "<digits><stat-word>" shape,
# so we drop them from the account enumeration.
_STAT_RE = re.compile(
    r"^\d+\s*(posts?|followers?|following|abonn\w*|abonn[ée]s?|publications?|mentions?|reels?|tagged)$",
    re.IGNORECASE,
)


class InstagramSwitchAccount:
    """Instagram account switcher, across the already logged-in accounts."""

    MAX_LOGOUT_LOOPS = 3  # guards the auto-switch-to-home loop

    def __init__(
        self,
        device,
        device_id: str,
        notifier: Optional[Callable[[str], None]] = None,
        on_active_account: Optional[Callable[[str], None]] = None,
        on_step: Optional[Callable[[str, dict], None]] = None,
        max_attempts: int = 2,
        transition_timeout: float = 10.0,
        poll_interval: float = 0.5,
        sleeper: Optional[Callable[[float], None]] = None,
        clock: Optional[Callable[[], float]] = None,
    ):
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(module="instagram-switch-account")
        self.auth = AUTH_SELECTORS
        # Reuse the logout navigation (profile tab → options menu → log out → dialogs).
        self._logout = InstagramLogout(device, device_id)
        self._notify = notifier or (lambda _msg: None)
        # Emit the currently-active account (@username) once detected, so the bridge/front recale the
        # device↔account DB link (account_device_history). No-op by default — e.g. the Cartography
        # Lab builds the manager without it and just reads the return value.
        self._emit_active = on_active_account or (lambda _u: None)
        # Emit the current workflow STEP (structured id + data) for the Taktik Agent panel narration
        # (one card per step: navigate_profile / active_account / logout / enumerate / select /
        # switched / relogin). No-op by default (Lab / tests).
        self._emit_step_cb = on_step or (lambda _step, _data: None)
        self.max_attempts = max(1, int(max_attempts))
        self.transition_timeout = max(0.0, float(transition_timeout))
        self.poll_interval = max(0.01, float(poll_interval))
        self._sleep = sleeper or time.sleep
        self._clock = clock or time.monotonic

    def _emit_step(self, step: str, **data) -> None:
        self._emit_step_cb(step, data)

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
        return normalize_account_username(username)

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
            # Skip the Android system UI (status bar / nav bar: "Back", "Home"/"Accueil"…) — only
            # Instagram's own nodes can be account rows.
            if re.search(r'package="(?:com\.android\.|android)', chunk):
                continue
            match = re.search(r'content-desc="([^"]*)"', chunk)
            if not match:
                continue
            desc = html.unescape(match.group(1)).strip()
            if desc:
                labels.append(desc)
        return labels

    def _account_catalog_from_labels(self, labels: List[str]) -> AccountCatalog:
        """Filter clickable content-descs down to the connected-account usernames.

        Each row's content-desc is the username (sometimes suffixed with ",  New notifications").
        Non-account buttons and the profile stats that leak behind the sheet are filtered out.
        """
        exclude = {label.lower() for label in self.auth.account_row_exclude_labels}
        found: List[str] = []
        for desc in labels:
            # Drop a trailing ",  New notifications" / ", Nouvelles notifications".
            name = desc.split(",")[0].strip()
            low = name.lower()
            if not name or low in exclude:
                continue
            # A username has no spaces (handles use letters/digits/._ only) and is never a
            # profile stat ("36followers") or a story label ("x's story").
            if " " in name or "'s story" in low or _STAT_RE.match(name):
                continue
            found.append(name)
        return AccountCatalog.from_values(found)

    def _accounts_from_labels(self, labels: List[str]) -> List[str]:
        return list(self._account_catalog_from_labels(labels).accounts)

    def _account_catalog_on_screen(self) -> AccountCatalog:
        return self._account_catalog_from_labels(self._clickable_labels())

    def _list_accounts_on_screen(self) -> List[str]:
        """The connected-account usernames visible on the current screen (one UI dump)."""
        return list(self._account_catalog_on_screen().accounts)

    def _switcher_is_open(self) -> bool:
        """The account switcher sheet / picker is open (shows the "Use another profile" button)."""
        return self._element_exists(self.auth.account_picker_indicators)

    def _on_landing_account_list(self) -> bool:
        """We are on the connected-accounts picker (the logged-out screen IG opens on directly).
        STRICT signal: the "Use another profile" button — NOT the presence of clickable rows, which
        would also match the home-feed bottom nav (Reels/Message/Profile) and mis-read as accounts."""
        return self._on_account_picker()

    def _open_account_switcher(self) -> bool:
        """Open the account switcher WITHOUT logging out: tap the @username (+ chevron) at the top
        of the Profile page. Kept call-light (slow device + scrcpy): find the button once, tap
        once, settle, confirm once. The caller enumerates regardless of the return value."""
        button = None
        for _ in range(6):
            button = self._find_element(self.auth.profile_username_switcher_button)
            if button is not None:
                break
            self._sleep(0.6)
        if button is None:
            self.logger.warning("account switcher: profile @username button not found")
            self._notify("Profile @username button not found")
            return False
        self._notify("Tapping @username to open the switcher…")
        try:
            button.click()
            self.logger.info("account switcher: tapped profile @username")
        except Exception as exc:
            self.logger.warning(f"account switcher: tap failed: {exc}")
            self._notify(f"Tap failed: {exc}")
            return False
        return bool(self._wait_until(self._switcher_is_open, self.transition_timeout))

    def _select_account(self, target: str) -> bool:
        clean = self._norm(target)
        if not is_account_username(clean):
            return False
        for selector in self.auth.exact_saved_profile_tile_selectors(clean):
            if self._click_first_match([selector], f"account @{clean}"):
                return True
        return False

    def _wait_until(self, condition: Callable[[], object], timeout: float):
        """Poll an observable UI condition under one total monotonic deadline."""
        deadline = self._clock() + max(0.0, timeout)
        while True:
            value = condition()
            if value:
                return value
            remaining = deadline - self._clock()
            if remaining <= 0:
                return None
            self._sleep(min(self.poll_interval, remaining))

    def _close_account_switcher(self) -> bool:
        """Close the non-destructive profile switcher and confirm it disappeared."""
        if not self._switcher_is_open():
            return True
        try:
            self.device.press("back")
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"Account switch recovery stage=close failed: {exc}")
            return False
        return bool(
            self._wait_until(
                lambda: not self._switcher_is_open(),
                min(self.transition_timeout, 3.0),
            )
        )

    def _wait_for_selected_account(self, target: str) -> tuple[str, Optional[str]]:
        """Wait for login expiry or a readable active username after selecting a row."""
        deadline = self._clock() + self.transition_timeout
        last_active: Optional[str] = None
        while True:
            if self._password_required():
                return "session_expired", last_active
            try:
                active = self.detect_active_account()
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(f"Account switch target=@{target} stage=verify read failed: {exc}")
                active = None
            if active:
                last_active = active
                if active == target:
                    return "verified", active
            remaining = deadline - self._clock()
            if remaining <= 0:
                return "verification_failed", last_active
            self._sleep(min(self.poll_interval, remaining))

    def _logout_to_picker_for_switch(self) -> tuple[bool, Optional[str], Optional[str]]:
        """Compatibility fallback retaining the switcher's historical error codes."""
        if not self._logout._open_profile_tab():
            return False, "profile_tab_not_found", "profile_tab"
        if not self._logout._open_options_menu():
            return False, "options_menu_not_found", "options_menu"
        if not self._logout._find_and_click_logout():
            return False, "logout_button_not_found", "logout_button"
        if not self._logout._confirm_logout():
            return False, "logout_confirm_failed", "logout_confirm"
        if not self._ensure_on_picker():
            return False, "picker_unreachable", "open_picker"
        return True, None, None

    def _failure(
        self,
        *,
        target: str,
        message: str,
        error_type: str,
        stage: str,
        category: str,
        attempts: int,
        active: Optional[str],
        accounts: List[str],
        state_known: bool,
        relogin_required: bool = False,
        previous: Optional[str] = None,
    ) -> SwitchResult:
        self.logger.warning(
            f"Account switch current=@{active or '?'} target=@{target} "
            f"attempt={attempts}/{self.max_attempts} stage={stage} error={error_type}"
        )
        return SwitchResult(
            False,
            message,
            error_type,
            switched_to=target if relogin_required else None,
            relogin_required=relogin_required,
            detected_accounts=accounts,
            requested_username=target,
            previous_username=previous,
            active_username=active,
            attempts=attempts,
            failure_stage=stage,
            failure_category=category,
            state_known=state_known,
        )

    def _restore_previous_account(
        self,
        previous: Optional[str],
        catalog: AccountCatalog,
    ) -> Optional[str]:
        """Best-effort restoration after the compatibility logout fallback."""
        if not previous or not catalog.contains(previous) or catalog.is_ambiguous(previous):
            return None
        self.logger.info(
            f"Account switch current=@? target=@{previous} attempt=0 stage=restore_previous"
        )
        if not self._select_account(previous):
            return None
        outcome, active = self._wait_for_selected_account(previous)
        return active if outcome == "verified" else None

    def _logged_in_now(self) -> bool:
        """We are logged in (home feed) and NOT on the picker → the switch landed."""
        return self._on_home_feed() and not self._on_account_picker()

    def _reach_login_navigation(self) -> bool:
        return self._logout._open_profile_tab() and self._logout._open_options_menu()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def _read_profile_username(self) -> Optional[str]:
        """Navigate to the own profile tab and read the logged-in @username, reusing the production
        atomics `navigate_to_profile_tab()` (robust: 3 tries, back if on another user's profile) +
        `get_username_from_profile()`. Isolated so `detect_active_account` can be unit-tested without
        a real device."""
        from ...actions.atomic.navigation import NavigationActions
        from ...actions.atomic.detection import DetectionActions

        nav = NavigationActions(self.device)
        detection = DetectionActions(self.device)
        if not nav.navigate_to_profile_tab():
            self.logger.warning("detect_active_account: could not reach the own profile")
            return None
        return detection.get_username_from_profile()

    def detect_active_account(self) -> Optional[str]:
        """Read the @username of the account currently ACTIVE on the device — non-destructive.

        Flow: when an account is active (home feed), navigate to the own profile tab and
        read the logged-in username. Emits `active_account_detected` (via the `on_active_account`
        callback) so the front recales the device↔account DB link. Returns None when logged out (on
        the picker there is no active account) or when the username can't be read / isn't a handle.
        """
        if self._on_account_picker():
            return None
        self._notify("Reading the active account from the profile…")
        self._emit_step("navigate_profile")
        try:
            raw = self._read_profile_username()
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"detect_active_account failed: {exc}")
            return None
        username = self._norm(raw)
        if not is_account_username(username):
            self.logger.warning(f"detect_active_account: no valid username (got {raw!r})")
            return None
        self.logger.info(f"👤 Active account on device: @{username}")
        self._notify(f"Active account on this device: @{username}")
        self._emit_step("active_account", username=username)
        self._emit_active(username)
        return username

    def switch_to(self, target_username: str) -> SwitchResult:
        target = self._norm(target_username)
        if not target:
            return SwitchResult(
                False,
                "No target username",
                "no_target",
                failure_stage="validate",
                failure_category="account_not_found",
                state_known=False,
            )
        if not is_account_username(target):
            return SwitchResult(
                False,
                f"@{target} is not a valid Instagram username",
                "invalid_target",
                requested_username=target,
                failure_stage="validate",
                failure_category="account_not_found",
                state_known=False,
            )

        self.logger.info(f"Account switch current=@? target=@{target} attempt=0 stage=detect")
        self._notify(f"Switching to @{target}")
        on_picker = self._on_landing_account_list()
        active = None if on_picker else self.detect_active_account()
        previous = active
        if active == target:
            self.logger.info(f"Account switch current=@{active} target=@{target} attempt=0 stage=noop")
            return SwitchResult(
                True,
                f"@{target} is already active",
                switched_to=target,
                requested_username=target,
                previous_username=active,
                active_username=active,
                already_active=True,
                attempts=0,
                state_known=True,
            )

        detected: List[str] = []
        last_failure: Optional[SwitchResult] = None
        logout_fallback_used = False

        for attempt in range(1, self.max_attempts + 1):
            self.logger.info(
                f"Account switch current=@{active or '?'} target=@{target} "
                f"attempt={attempt}/{self.max_attempts} stage=open"
            )
            source = "picker"
            destructive_picker = bool(logout_fallback_used)
            if not self._on_landing_account_list():
                destructive_picker = False
                if self._open_account_switcher():
                    source = "switcher"
                elif not logout_fallback_used:
                    logout_fallback_used = True
                    self._notify("Opening the saved-account picker…")
                    self._emit_step("logout", attempt=attempt)
                    reached, error_type, stage = self._logout_to_picker_for_switch()
                    if not reached:
                        last_failure = self._failure(
                            target=target,
                            message="Account picker not reached",
                            error_type=error_type or "picker_unreachable",
                            stage=stage or "open_picker",
                            category="ui_navigation_failure",
                            attempts=attempt,
                            active=active,
                            accounts=detected,
                            state_known=bool(active),
                            previous=previous,
                        )
                        continue
                    active = None
                    destructive_picker = True
                else:
                    last_failure = self._failure(
                        target=target,
                        message="Account switcher could not be opened",
                        error_type="switcher_unavailable",
                        stage="open_switcher",
                        category="selector_not_found",
                        attempts=attempt,
                        active=active,
                        accounts=detected,
                        state_known=bool(active),
                        previous=previous,
                    )
                    continue

            catalog = self._account_catalog_on_screen()
            detected = list(catalog.accounts)
            self._emit_step("enumerate", accounts=detected, attempt=attempt)
            if catalog.is_ambiguous(target):
                if source == "switcher":
                    self._close_account_switcher()
                elif destructive_picker:
                    active = self._restore_previous_account(previous, catalog)
                return self._failure(
                    target=target,
                    message=f"Multiple account rows match @{target}",
                    error_type="ambiguous_target",
                    stage="lookup",
                    category="account_not_found",
                    attempts=attempt,
                    active=active,
                    accounts=detected,
                    state_known=bool(active) or source == "picker",
                    previous=previous,
                )
            if not catalog.contains(target):
                if source == "switcher":
                    self._close_account_switcher()
                elif destructive_picker:
                    active = self._restore_previous_account(previous, catalog)
                return self._failure(
                    target=target,
                    message=f"@{target} is not connected on this device",
                    error_type="target_not_connected",
                    stage="lookup",
                    category="account_not_found",
                    attempts=attempt,
                    active=active,
                    accounts=detected,
                    state_known=bool(active) or source == "picker",
                    previous=previous,
                )

            self._emit_step("select", username=target, attempt=attempt)
            if not self._select_account(target):
                if source == "switcher":
                    self._close_account_switcher()
                last_failure = self._failure(
                    target=target,
                    message=f"Could not tap @{target}",
                    error_type="select_failed",
                    stage="select",
                    category="selector_not_found",
                    attempts=attempt,
                    active=active,
                    accounts=detected,
                    state_known=bool(active) or source == "picker",
                    previous=previous,
                )
                continue

            outcome, observed = self._wait_for_selected_account(target)
            if outcome == "session_expired":
                self._emit_step("relogin", username=target, attempt=attempt)
                return self._failure(
                    target=target,
                    message=f"@{target} requires re-login (session expired or not saved)",
                    error_type="session_expired",
                    stage="verify",
                    category="login_session_expired",
                    attempts=attempt,
                    active=observed,
                    accounts=detected,
                    state_known=True,
                    relogin_required=True,
                    previous=previous,
                )
            if outcome == "verified":
                self._emit_step("switched", username=target, attempt=attempt)
                self.logger.info(
                    f"Account switch current=@{observed} target=@{target} "
                    f"attempt={attempt}/{self.max_attempts} stage=verified"
                )
                return SwitchResult(
                    True,
                    f"Switched to @{target}",
                    switched_to=target,
                    detected_accounts=detected,
                    requested_username=target,
                    previous_username=previous,
                    active_username=observed,
                    attempts=attempt,
                    state_known=True,
                )

            # A row tap may have changed the active session. Never report the pre-switch
            # identity as current unless it was observed again after that destructive action.
            active = observed
            last_failure = self._failure(
                target=target,
                message=f"Instagram did not verify @{target} after selection",
                error_type="verification_failed",
                stage="verify",
                category="switch_verification_failed",
                attempts=attempt,
                active=active,
                accounts=detected,
                state_known=bool(active) or self._on_account_picker(),
                previous=previous,
            )

        return last_failure or self._failure(
            target=target,
            message="Account switch attempts exhausted",
            error_type="switcher_unavailable",
            stage="open_switcher",
            category="ui_navigation_failure",
            attempts=self.max_attempts,
            active=active,
            accounts=detected,
            state_known=bool(active),
            previous=previous,
        )

    def list_accounts(self) -> List[str]:
        """List the Instagram accounts logged in on the device — NON-destructive.

        When the accounts are logged out, IG opens directly on the account picker: enumerate it
        as-is. When an account is ACTIVE (home feed), the full picker is only reachable by logging
        out, which we must NOT do for a mere read. Instead READ the active
        account (navigate to the own profile) and return just that one — recaling the device↔account
        DB link via `active_account_detected`. The bottom-nav tabs on the home feed are NOT accounts.
        """
        self.logger.info("📋 Listing connected accounts")
        self._notify("Reading connected accounts…")
        time.sleep(1.5)  # let IG settle after launch
        if not self._on_account_picker():
            self.logger.info("list_accounts: an account is active → reading it from the profile")
            active = self.detect_active_account()
            return [active] if active else []
        accounts = self._list_accounts_on_screen()
        self.logger.info(f"📋 {len(accounts)} connected account(s): {accounts}")
        self._notify(f"Detected {len(accounts)} account(s): {accounts}")
        return accounts

    def list_saved_accounts(self) -> List[str]:
        """List ALL accounts saved on the device — DESTRUCTIVE.

        When an account is active, the only screen that shows every saved account is the logged-out
        picker, so we LOG OUT to reach it (logout → account list → choice)
        then enumerate. We recale the DB with the active account BEFORE logging out, and leave the
        device ON the picker so a following `switch_to(target)` selects the account directly (no
        second logout). If already on the picker, just enumerate.
        """
        self.logger.info("📋 Listing ALL saved accounts (logout → picker)")
        self._notify("Listing all saved accounts (this logs out to open the account picker)…")
        time.sleep(1.5)  # let IG settle after launch
        if not self._on_account_picker():
            # An account is active: recale the DB with it, then log out to reach the picker.
            self.detect_active_account()
            self._emit_step("logout")
            if not self._logout_to_picker():
                self.logger.warning("list_saved_accounts: could not reach the account picker")
                self._notify("Could not reach the account picker")
                return []
        accounts = self._list_accounts_on_screen()
        self.logger.info(f"📋 {len(accounts)} saved account(s): {accounts}")
        self._notify(f"Detected {len(accounts)} saved account(s): {accounts}")
        self._emit_step("enumerate", accounts=accounts)
        return accounts

    def _logout_to_picker(self) -> bool:
        """Log out (Profile tab → options menu → Log out → confirm dialogs) and reach the
        connected-accounts picker, handling Instagram auto-switching to another account's home
        (bounded re-logout via `_ensure_on_picker`). Reuses the InstagramLogout navigation. Returns
        True if we land on the picker; no-op → True if already there."""
        if self._on_account_picker():
            return True
        if not (self._logout._open_profile_tab()
                and self._logout._open_options_menu()
                and self._logout._find_and_click_logout()):
            return False
        self._logout._confirm_logout()
        time.sleep(3)
        return self._ensure_on_picker()

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
                    # Re-logout nav failed (transient UI, e.g. IG still animating the auto-switch) —
                    # wait and retry within the bounded loop instead of giving up early; the picker
                    # may still settle in on the next iteration.
                    time.sleep(1.5)
                    continue
                self._logout._confirm_logout()
                time.sleep(3)
                continue
            # Transitional screen → give it a moment.
            time.sleep(1.5)
        return self._on_account_picker()


__all__ = ["InstagramSwitchAccount", "SwitchResult"]
