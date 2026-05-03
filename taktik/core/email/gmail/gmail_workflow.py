"""
Gmail Workflow

Standalone, platform-agnostic workflow for:
  1. Ensuring a Gmail account is present on the device
     (adds it via the Gmail app if absent).
  2. Retrieving the latest OTP / verification code sent to that inbox.

Designed to be called from any signup workflow (TikTok, Instagram, Threads…).

Architecture
------------
The Google sign-in screen (email + password) is rendered inside a WebView
owned by com.google.android.gms.  Elements INSIDE the WebView are not
accessible via uiautomator2 selectors.  Interaction with those fields is
done by:
  1. Resolving the WebView bounds from the UI hierarchy.
  2. Tapping on the approximate absolute coordinates of each input field
     (derived from device screen dimensions — see _WEBVIEW_EMAIL_Y_RATIO /
     _WEBVIEW_PASSWORD_Y_RATIO constants).
  3. Using device.send_keys() to type once the field is focused.

The "Suivant"/"Next" button sits OUTSIDE the WebView in the gms layout and
IS accessible by text.

Screen states handled
---------------------
  SWITCHER       – Gmail account overlay (avatar tapped)
  SETUP          – "Configurez votre adresse e-mail" provider list
  GOOGLE_SIGNIN  – Google WebView "Connexion" (email entry)
  GOOGLE_PASSWORD – Google WebView password entry
  GOOGLE_TERMS   – Google ToS / "J'accepte"
  INBOX          – Gmail main inbox view
  UNKNOWN        – fallback / intermediate screen
"""
import re
import time
from typing import Optional

from loguru import logger
from bridges.common.ipc import IPC
from taktik.core.email.gmail.selectors import (
    GMAIL_SWITCHER_SELECTORS,
    GMAIL_SETUP_SELECTORS,
    GOOGLE_SIGNIN_SELECTORS,
    GOOGLE_VERIFY_SELECTORS,
    GOOGLE_RECOVERY_SELECTORS,
    GMAIL_INBOX_SELECTORS,
)

_ipc = IPC()

_GMAIL_PACKAGE = "com.google.android.gm"

# Maximum state-machine iterations for add_account
_MAX_ACCOUNT_ITERATIONS = 25
# Maximum wait time for a new email to arrive (seconds)
_OTP_POLL_TIMEOUT = 120
# Interval between inbox refresh polls (seconds)
_OTP_POLL_INTERVAL = 5
# Timeout for quick element-existence checks (seconds)
# NOTE: used only for click confirmations — screen detection uses dump_hierarchy()
_EXIST_TIMEOUT = 1.5
# Pause after each navigation action
_NAV_PAUSE = 1.0

# WebView layout constants
# The Google sign-in WebView fills the area between the status bar and the
# "Suivant" button row.  Input-field Y positions are expressed as a fraction
# of the screen HEIGHT so they stay valid across different DPI / resolution.
#
# Calibrated on a 576×1280 device (dumps 20260502):
#   – Email field visually at y ≈ 505  → ratio ≈ 0.395
#   – Password field visually at y ≈ 505 (same position on the password screen)
_WEBVIEW_INPUT_Y_RATIO = 0.395


class GmailWorkflow:
    """
    Platform-agnostic Gmail utility workflow.

    Parameters
    ----------
    device     : uiautomator2 device object
    device_id  : ADB serial / device identifier (for logging)
    """

    def __init__(self, device, device_id: str):
        self.device    = device
        self.device_id = device_id
        self.logger    = logger.bind(device=device_id)

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def ensure_account_added(self, email: str, password: str) -> dict:
        """
        Ensure *email* is added as a Google account in the Gmail app.

        If the account is already present, returns immediately with success.
        Otherwise opens Gmail, navigates to "Ajouter un autre compte" and
        goes through the Google sign-in WebView flow.

        Returns
        -------
        dict  {success: bool, message: str, error_type: str|None}
        """
        self.logger.info(f"📧 Ensuring Gmail account: {email}")
        _ipc.status("running", f"Checking Gmail account {email}…")

        try:
            # ── Open Gmail app ──────────────────────────────────────────
            _ipc.log("info", "📱 Opening Gmail…")
            # Dismiss any lingering GMS overlay from a previous run.
            # When GMS (Google sign-in WebView) is in the foreground and we call
            # app_start(Gmail), Gmail's task comes to front but GMS's activity is
            # still on top of it.  app_wait(front=True) then blocks for up to 30 s
            # because Gmail never becomes the front package.  Pressing BACK first
            # dismisses the GMS activity and returns to Gmail.
            try:
                pre_h = self.device.dump_hierarchy()
                if "com.google.android.gms" in pre_h:
                    self.logger.debug("Dismissing lingering GMS overlay before starting Gmail")
                    self.device.press("back")
                    time.sleep(1.5)
            except Exception:
                pass
            self.device.app_start(_GMAIL_PACKAGE)
            # Use a simple fixed sleep instead of app_wait(front=True, timeout=30).
            # app_wait blocks the full timeout when GMS is foregrounded on Gmail's
            # task stack (which is common after a partial previous run).
            time.sleep(2.5)

            # ── State machine: drive through add-account flow ───────────
            for iteration in range(_MAX_ACCOUNT_ITERATIONS):
                screen = self._detect_add_account_screen()
                _ipc.log("info", f"🔍 Gmail add-account [{iteration+1}/{_MAX_ACCOUNT_ITERATIONS}]: {screen}")
                self.logger.debug(f"Gmail add-account state: {screen}")

                if screen == "inbox":
                    # Fast check: if Gmail is already showing the target account
                    # we're done — no need to open the switcher at all.
                    # This covers both "account just added" and "already present"
                    # in a single dump read.
                    active = self._get_active_account_from_dump()
                    if active and email.lower() in active:
                        _ipc.log("info", f"✅ Gmail already on correct account: {email}")
                        return {"success": True,
                                "message": "Account active",
                                "error_type": None}
                    # Different account active — open switcher to add/switch
                    if not self._open_account_switcher():
                        return self._error("switcher_not_found",
                                           "Could not open Gmail account switcher")
                    time.sleep(_NAV_PAUSE)

                elif screen == "switcher":
                    # If the account is already present in Gmail, stop here.
                    try:
                        hierarchy = self.device.dump_hierarchy()
                        if email.lower() in hierarchy.lower():
                            _ipc.log("info", f"✅ Gmail account already in switcher: {email}")
                            self._click_selector(GMAIL_SWITCHER_SELECTORS.close, timeout=0.8)
                            return {"success": True, "message": "Account already present", "error_type": None}
                    except Exception:
                        pass

                    # Click "Ajouter un autre compte"
                    if not self._click_selector(GMAIL_SWITCHER_SELECTORS.add_account):
                        return self._error("add_account_not_found",
                                           "Could not find 'Ajouter un autre compte' button")
                    time.sleep(_NAV_PAUSE)

                elif screen == "setup":
                    # Click the "Google" provider row
                    if not self._click_selector(GMAIL_SETUP_SELECTORS.google_row):
                        # The Google row can disappear while transitioning to
                        # com.google.android.gms.  If that happened, do not fail.
                        next_screen = self._detect_add_account_screen()
                        if next_screen in ("google_signin", "google_password", "google_terms"):
                            _ipc.log("info", f"↪️ Gmail setup already moved to {next_screen}")
                            time.sleep(_NAV_PAUSE)
                            continue
                        return self._error("google_row_not_found",
                                           "Could not find Google provider in setup list")
                    time.sleep(_NAV_PAUSE)

                elif screen == "google_signin":
                    # Enter email in WebView (coordinate-based)
                    _ipc.log("info", f"⌨️  Entering email: {email}")
                    self._webview_tap_input()
                    time.sleep(0.5)
                    self.device.send_keys(email)
                    time.sleep(0.5)
                    # Click "Suivant"
                    if not self._click_selector(GOOGLE_SIGNIN_SELECTORS.next_button, timeout=6.0):
                        return self._error("signin_next_not_found",
                                           "Could not click Suivant after email entry")
                    _ipc.log("info", "✅ Email submitted")
                    time.sleep(_NAV_PAUSE)

                elif screen == "google_password":
                    # Enter password in WebView (same Y ratio — password field is at same position)
                    _ipc.log("info", "🔒 Entering password…")
                    self._webview_tap_input()
                    time.sleep(0.5)
                    self.device.send_keys(password)
                    time.sleep(0.5)
                    if not self._click_selector(GOOGLE_SIGNIN_SELECTORS.password_next_button, timeout=6.0):
                        return self._error("password_next_not_found",
                                           "Could not click Suivant after password entry")
                    _ipc.log("info", "✅ Password submitted")
                    time.sleep(_NAV_PAUSE * 2)  # Google auth can take a moment

                elif screen == "google_terms":
                    # Accept ToS
                    _ipc.log("info", "📜 Accepting Google Terms…")
                    if not self._click_selector(GOOGLE_SIGNIN_SELECTORS.accept_button, timeout=8.0):
                        # Try "Continuer" as alternative
                        if not self._click_selector(GOOGLE_SIGNIN_SELECTORS.continue_button, timeout=4.0):
                            return self._error("tos_accept_not_found",
                                               "Could not accept Google Terms of Service")
                    time.sleep(_NAV_PAUSE)

                elif screen == "google_verify_identity":
                    # Google wants to verify our identity (new device heuristic).
                    # Best automated path: request a validation code at the
                    # recovery email shown on screen.
                    _ipc.log("info", "🔐 Google identity challenge — selecting 'Receive code'…")
                    if not self._click_selector(GOOGLE_VERIFY_SELECTORS.receive_code, timeout=5.0):
                        # Fallback: tap on the first option by coordinate
                        # The list starts around y=575 on 576×1280; center ≈ (288,632)
                        try:
                            info = self.device.info
                            w = int(info.get("displayWidth", 576))
                            h_px = int(info.get("displayHeight", 1280))
                            tap_y = int(h_px * 0.494)  # ≈ 632 / 1280
                            self.device.click(w // 2, tap_y)
                        except Exception:
                            self.device.click(288, 632)
                    time.sleep(_NAV_PAUSE)

                elif screen == "google_verify_send":
                    # Confirmation step: Google shows the masked recovery email
                    # and a 'Envoyer' button to actually dispatch the code.
                    _ipc.log("info", "📨 Confirming code send (Envoyer)…")
                    if not self._click_selector(GOOGLE_VERIFY_SELECTORS.send_button, timeout=5.0):
                        return self._error("verify_send_not_found",
                                           "Could not click Envoyer on code confirmation screen")
                    time.sleep(_NAV_PAUSE * 2)

                elif screen == "google_verify_otp":
                    # Code entry screen reached — the bot cannot read the code
                    # automatically (it's in the recovery email inbox, not in
                    # the Gmail we're trying to add). Return a specific error
                    # type so the front-end can prompt the user.
                    return self._error(
                        "awaiting_verification_code",
                        "Google sent a verification code to the recovery email. "
                        "Please provide the code via the front-end."
                    )

                elif screen == "google_recovery_options":
                    # Google offers to add a recovery phone number.
                    # Skip by clicking "Annuler" — no phone needed.
                    _ipc.log("info", "📵 Skipping recovery phone (Annuler)…")
                    if not self._click_selector(GOOGLE_RECOVERY_SELECTORS.cancel_button, timeout=5.0):
                        # Fallback: coordinate tap on Annuler button
                        # From dump: bounds [24,1153][127,1208] → center ≈ (75, 1180)
                        try:
                            info = self.device.info
                            h_px = int(info.get("displayHeight", 1280))
                            self.device.click(75, int(h_px * 0.922))
                        except Exception:
                            self.device.click(75, 1180)
                    time.sleep(_NAV_PAUSE)

                elif screen == "google_error":
                    return self._error("google_signin_error",
                                       "Google sign-in rejected credentials or triggered CAPTCHA")

                elif screen == "account_added":
                    # Gmail shows the inbox for the newly added account
                    _ipc.log("info", f"✅ Gmail account added: {email}")
                    return {"success": True, "message": f"Account {email} added", "error_type": None}

                else:
                    # UNKNOWN — wait and retry
                    self.logger.debug(f"Gmail add-account: unknown screen at iteration {iteration+1}")
                    time.sleep(_NAV_PAUSE)

            return self._error("max_iterations",
                               f"Could not add Gmail account after {_MAX_ACCOUNT_ITERATIONS} iterations")

        except Exception as exc:
            self.logger.exception("💥 Gmail ensure_account_added failed")
            _ipc.log("error", f"❌ Gmail error: {exc}")
            return {"success": False, "message": str(exc), "error_type": "exception"}

    def get_latest_verification_code(
        self,
        email: str,
        sender_filter: Optional[str] = None,
        subject_filter: Optional[str] = None,
        timeout: int = _OTP_POLL_TIMEOUT,
    ) -> dict:
        """
        Poll the Gmail inbox until a verification code email arrives, then
        extract and return the 6-digit code.

        Parameters
        ----------
        email          : Gmail account to check
        sender_filter  : partial sender name/address to filter (e.g. "TikTok")
        subject_filter : partial subject to filter (e.g. "verification")
        timeout        : max seconds to wait for the email (default 120)

        Returns
        -------
        dict  {success: bool, code: str|None, message: str, error_type: str|None}
        """
        self.logger.info(f"📬 Waiting for verification code in {email}…")
        _ipc.status("running", "Waiting for verification email…")

        try:
            # Open Gmail on the correct account
            result = self._switch_to_account(email)
            if not result["success"]:
                return result

            # Poll the inbox
            search_query = self._build_search_query(sender_filter, subject_filter)
            deadline = time.time() + timeout

            while time.time() < deadline:
                code = self._search_and_extract_code(search_query)
                if code:
                    _ipc.log("info", f"✅ Verification code found: {code}")
                    return {
                        "success": True,
                        "code": code,
                        "message": f"Code found: {code}",
                        "error_type": None,
                    }
                remaining = int(deadline - time.time())
                _ipc.log("info", f"⏳ No code yet — retrying (timeout in {remaining}s)…")
                time.sleep(_OTP_POLL_INTERVAL)

            return {
                "success": False,
                "code": None,
                "message": f"Timed out after {timeout}s waiting for verification code",
                "error_type": "timeout",
            }

        except Exception as exc:
            self.logger.exception("💥 Gmail get_latest_verification_code failed")
            _ipc.log("error", f"❌ Gmail OTP error: {exc}")
            return {"success": False, "code": None, "message": str(exc), "error_type": "exception"}

    # ──────────────────────────────────────────────────────────────────
    # Screen detection
    # ──────────────────────────────────────────────────────────────────

    def _detect_add_account_screen(self) -> str:
        """
        Detect the current screen during the add-account flow.

        Uses a SINGLE dump_hierarchy() call + text/id matching to avoid the
        O(N×timeout) cost of sequential xpath.wait() calls.  Each unknown
        iteration now costs ~0.5–1 s (one dump) instead of ~40–50 s.

        Priority order:
          1. google_error      – sign-in rejection / wrong credentials
          2. google_terms      – ToS acceptance screen
          3. google_password   – password WebView ("mot de passe" in dump)
          4. google_signin     – email WebView (gms + Suivant, no password hint)
          5. setup             – Gmail provider selection
          6. switcher          – Gmail account overlay
          7. inbox             – Gmail inbox / any Gmail foreground screen
          8. unknown           – Gmail not yet visible in hierarchy
        """
        try:
            h = self.device.dump_hierarchy()
        except Exception:
            return "unknown"

        hl = h.lower()

        # 1. Sign-in error (wrong credentials / blocked)
        if ("com.google.android.gms" in h and
                any(x in hl for x in ("incorrect", "inexact", "wrong"))):
            return "google_error"

        # 2 & 3 & 4. Any GMS screen (ToS / email / password WebViews)
        if "com.google.android.gms" in h:
            # 2. Terms of Service
            if any(x in h for x in ("J'accepte", "I agree", "Accepter", "Accept")):
                return "google_terms"
            # 3. Identity verification challenge ("Confirmez qu'il s'agit bien de vous")
            if ("confirmez qu'il s'agit bien de vous" in hl
                    or "choisissez comment vous connecter" in hl
                    or "verify it's you" in hl
                    or "confirm it's you" in hl):
                return "google_verify_identity"
            # Recovery options screen ("Assurez-vous de toujours pouvoir vous connecter")
            if ("account recovery options" in hl
                    or "assurez-vous de toujours pouvoir vous connecter" in hl
                    or "ajoutez un numéro de téléphone de récupération" in hl):
                return "google_recovery_options"
            # 4. Send-confirmation step after choosing receive-code option
            #    (screen shows masked recovery email + "Envoyer" button)
            if any(x in h for x in ("Envoyer", "Send")):
                if "recevoir" in hl or "envoy" in hl or "code" in hl:
                    return "google_verify_send"
            # 5. OTP code entry screen (input field for the received code)
            if 'resource-id="verificationCode"' in h or 'resource-id="totpPin"' in h:
                return "google_verify_otp"
            # Direct IDs from the 2026-05-02 dump. These are more reliable
            # than localized text and avoid confusing the Google sign-in page
            # with Gmail provider setup.
            if 'resource-id="identifierId"' in h:
                return "google_signin"
            if ('resource-id="Passwd"' in h or 'resource-id="password"' in h or
                    "saisissez votre mot de passe" in hl or "enter your password" in hl):
                return "google_password"
            # 3 & 4. Sign-in WebView — "Suivant"/"Next" is the only accessible button
            if any(x in h for x in ("Suivant", "Next")):
                # Distinguish email step from password step via text hints in the dump
                if "mot de passe" in hl or "password" in hl:
                    return "google_password"
                # Only sign-in if not on the Gmail setup screen
                if "configurez votre adresse" not in hl and "set up email" not in hl:
                    return "google_signin"
            # GMS is present but its WebView hasn't finished loading yet —
            # do NOT fall through to Gmail checks (that would wrongly return
            # "inbox" because com.google.android.gm is still in the dump as
            # a background package).  Wait another iteration instead.
            return "unknown"

        # 5. Gmail provider setup ("Configurez votre adresse e-mail")
        if "configurez votre adresse e-mail" in hl or "set up email" in hl:
            return "setup"

        # 6. Account switcher overlay
        if ("og_bento_account_menu_title_text" in h or
                "og_bento_selected_account_greeting_message" in h):
            return "switcher"

        # 7. Gmail inbox or any Gmail foreground screen
        if ("com.google.android.gm:id/search_bar" in h or
                "com.google.android.gm:id/conversation_list_view" in h):
            return "inbox"
        # Gmail is in foreground but specific view not yet identified
        # (e.g. loading spinner or initial splash) — try opening switcher
        if "com.google.android.gm" in h:
            return "inbox"

        return "unknown"

    # ──────────────────────────────────────────────────────────────────
    # Account management helpers
    # ──────────────────────────────────────────────────────────────────

    def _account_exists_in_system(self, email: str) -> bool:
        """
        Check if *email* is registered in the Android accounts system via ADB.
        Uses 'adb shell content query' on the accounts database.
        Non-blocking: returns False on any error.
        """
        try:
            result = self.device.shell(
                "content query --uri content://com.android.email.provider/account"
            )
            if email.lower() in result.lower():
                return True
            # Also check via the accounts manager (broader)
            result2 = self.device.shell("dumpsys account | grep -i " + email.split("@")[0])
            return email.lower() in result2.lower()
        except Exception:
            return False

    def _account_visible_in_switcher(self, email: str) -> bool:
        """
        Open the Gmail account switcher and check if *email* is listed.
        Closes the switcher afterwards.  Returns False on any error.
        """
        try:
            if not self._open_account_switcher():
                return False
            time.sleep(0.8)
            hierarchy = self.device.dump_hierarchy()
            found = email.lower() in hierarchy.lower()
            # Close the switcher
            self._click_selector(GMAIL_SWITCHER_SELECTORS.close)
            time.sleep(0.5)
            return found
        except Exception:
            return False

    def _open_account_switcher(self) -> bool:
        """Tap the avatar to open the account switcher from the Gmail inbox."""
        # Fast path: current Gmail versions expose the avatar as
        # com.google.android.gm:id/selected_account_disc_gmail.
        if self._click_selector(GMAIL_SWITCHER_SELECTORS.avatar, timeout=0.8):
            time.sleep(0.6)
            if self._is_switcher_open():
                return True

        # Fallback from real dump (576×1280): avatar bounds [492,54][570,127],
        # center ≈ (531,90). Use ratios for other resolutions.
        try:
            info = self.device.info
            width = int(info.get("displayWidth", 576))
            height = int(info.get("displayHeight", 1280))
        except Exception:
            width, height = 576, 1280

        candidates = [
            (int(width * 0.922), int(height * 0.070)),
            (width - 45, int(height * 0.070)),
            (width - 45, 90),
        ]
        for x, y in candidates:
            try:
                self.logger.debug(f"Gmail switcher fallback tap at ({x}, {y})")
                self.device.click(x, y)
                time.sleep(0.7)
                if self._is_switcher_open():
                    return True
            except Exception:
                continue

        return False

    def _is_switcher_open(self) -> bool:
        """Fast check for the Gmail account switcher overlay."""
        try:
            h = self.device.dump_hierarchy()
        except Exception:
            return False
        hl = h.lower()
        return (
            "og_bento_account_menu_title_text" in h
            or "og_bento_selected_account_greeting_message" in h
            or "ajouter un autre compte" in hl
            or "add another account" in hl
            or "changer de compte" in hl
            or "switch account" in hl
        )

    def _switch_to_account(self, email: str) -> dict:
        """
        Open Gmail and switch to *email* if it is not the active account.
        Assumes the account is already added (call ensure_account_added first).

        Fast path: reads selected_account_disc_gmail content-desc from a UI
        dump.  On this version of Gmail the content-desc is:
          "Connect\u00e9 en tant que <Name> <email>\\nCompte et param\u00e8tres."
        so we can detect the active account without opening the switcher at all.
        """
        _ipc.log("info", f"\ud83d\udd04 Switching Gmail to account: {email}")
        self.device.app_start(_GMAIL_PACKAGE)
        time.sleep(1.5)

        # ── Fast path: already on the correct account? ─────────────────
        active = self._get_active_account_from_dump()
        if active and email.lower() in active:
            _ipc.log("info", f"\u2705 Gmail already on correct account: {email}")
            return {"success": True, "message": "Correct account active", "error_type": None}

        # ── Need to switch — open the account switcher ──────────────────
        if not self._open_account_switcher():
            _ipc.log("warning", "\u26a0\ufe0f Could not open account switcher \u2014 proceeding with current account")
            return {"success": True, "message": "Using current account", "error_type": None}

        time.sleep(0.8)

        # Dump the switcher once and use it for all checks
        try:
            hierarchy = self.device.dump_hierarchy()
        except Exception:
            hierarchy = ""

        # Email might be the already-active account shown in the switcher header.
        # In that case just close the overlay and return.
        if email.lower() in hierarchy.lower():
            # Check secondary rows first (non-active accounts)
            rows = self.device.xpath(
                '//*[@resource-id="com.google.android.gm:id/og_secondary_account_information"]'
            ).all()
            for row in rows:
                row_text = (row.info.get("text") or "").lower()
                if email.lower() in row_text:
                    row.click()
                    _ipc.log("info", f"\u2705 Switched to account: {email}")
                    time.sleep(1.5)
                    return {"success": True, "message": f"Switched to {email}", "error_type": None}

            # Email is in the dump but not in secondary rows — it must be the
            # currently-active account shown in the header.  Just close.
            _ipc.log("info", f"\u2705 Target account is already active in switcher: {email}")
            self._click_selector(GMAIL_SWITCHER_SELECTORS.close, timeout=2.0)
            time.sleep(0.5)
            return {"success": True, "message": "Correct account active", "error_type": None}

        # Account not found in switcher at all
        self._click_selector(GMAIL_SWITCHER_SELECTORS.close, timeout=2.0)
        return self._error("account_not_in_switcher",
                           f"Account {email} not found in Gmail switcher. "
                           "Call ensure_account_added() first.")

    def _get_active_account_from_dump(self) -> Optional[str]:
        """
        Return the email address of the currently active Gmail account,
        or None if it cannot be determined.

        Reads the content-desc of selected_account_disc_gmail which on this
        Gmail version is:
          "Connect\u00e9 en tant que <Name> <email>\\nCompte et param\u00e8tres."
        """
        try:
            h = self.device.dump_hierarchy()
            idx = h.find("selected_account_disc_gmail")
            if idx == -1:
                return None
            # content-desc is within the next ~400 chars
            node_str = h[idx: idx + 400]
            m = re.search(r'content-desc="([^"]+)"', node_str)
            if m:
                desc = m.group(1)
                email_match = re.search(r'[\w.+\-]+@[\w.+\-]+\.\w+', desc)
                if email_match:
                    return email_match.group(0).lower()
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────────────────────────────
    # OTP / inbox helpers
    # ──────────────────────────────────────────────────────────────────

    def _build_search_query(
        self,
        sender_filter: Optional[str],
        subject_filter: Optional[str],
    ) -> str:
        """Build a Gmail search query string from filters."""
        parts = []
        if sender_filter:
            parts.append(f"from:{sender_filter}")
        if subject_filter:
            parts.append(f"subject:{subject_filter}")
        if not parts:
            parts.append("verification code")
        return " ".join(parts)

    def _search_and_extract_code(self, query: str) -> Optional[str]:
        """
        Search Gmail for *query*, open the first result, and extract a
        6-digit OTP code from the message body.

        Returns the code string, or None if not found.
        """
        try:
            # Open search
            if not self._click_selector(GMAIL_INBOX_SELECTORS.search_bar, timeout=5.0):
                self.logger.warning("Gmail search bar not found — cannot search inbox")
                return None

            time.sleep(0.5)

            search_input = self._find_element(GMAIL_INBOX_SELECTORS.search_input, timeout=4.0)
            if not search_input:
                self.device.press("back")
                return None

            search_input.click()
            time.sleep(0.3)
            self.device.send_keys(query, clear=True)
            time.sleep(0.5)
            self.device.press("enter")
            time.sleep(2.0)

            # Tap the first conversation result
            first = self._find_element(GMAIL_INBOX_SELECTORS.first_conversation, timeout=5.0)
            if not first:
                # No results yet
                self.device.press("back")
                time.sleep(0.5)
                return None

            # Try to extract the code from the search-results list view FIRST.
            # The email subject (e.g. "647393 is your TikTok code") is always
            # visible as a plain TextView in the list — no WebView involved.
            list_hierarchy = self.device.dump_hierarchy()
            code = self._extract_otp(list_hierarchy)
            if code:
                # Code found in the list — no need to open the email.
                self.device.press("back")
                time.sleep(0.5)
                return code

            # Fallback: open the email and try reading from its full content.
            first.click()
            time.sleep(2.0)

            # Extract OTP from the hierarchy dump
            hierarchy = self.device.dump_hierarchy()
            code = self._extract_otp(hierarchy)

            # Navigate back to inbox
            self.device.press("back")
            time.sleep(0.5)
            self.device.press("back")
            time.sleep(0.5)

            return code

        except Exception as exc:
            self.logger.warning(f"_search_and_extract_code failed: {exc}")
            try:
                # Recover to inbox
                self.device.press("back")
                self.device.press("back")
            except Exception:
                pass
            return None

    def _extract_otp(self, hierarchy_xml: str) -> Optional[str]:
        """
        Extract a 6-digit code from a UI hierarchy XML string.

        Searches all `text` attribute values for:
          - A standalone 6-digit sequence
          - Common patterns: "code : 123456", "code is 123456"
        Returns the first match, or None.
        """
        # Priority 1: explicit patterns
        patterns = [
            r'\b(\d{6})\b',
            r'code\s*[:\-–]\s*(\d{6})',
            r'code\s+is\s+(\d{6})',
            r'code\s+est\s*[:\-–]?\s*(\d{6})',
        ]
        # Extract all text= attribute values then search
        texts = re.findall(r'text="([^"]+)"', hierarchy_xml)
        for text in texts:
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1)
        # Fallback: scan entire XML for any standalone 6-digit sequence
        match = re.search(r'\b(\d{6})\b', hierarchy_xml)
        if match:
            return match.group(1)
        return None

    # ──────────────────────────────────────────────────────────────────
    # WebView interaction
    # ──────────────────────────────────────────────────────────────────

    def _webview_tap_input(self):
        """
        Tap the center-X of the screen at the calculated Y position of the
        email/password input field inside the Google sign-in WebView.

        The input field is not accessible via uiautomator2 (it lives inside
        a WebView). We tap at an absolute coordinate derived from the device
        screen dimensions and the empirically calibrated Y ratio.
        """
        # On recent Google Play Services builds the WebView exposes usable
        # EditText nodes (dump 2026-05-02: resource-id="identifierId"). Use
        # them first; fall back to calibrated coordinates only if necessary.
        field = self._find_element([
            '//*[@resource-id="identifierId"]',
            '//*[@resource-id="Passwd"]',
            '//*[@resource-id="password"]',
            '//*[@package="com.google.android.gms" and @class="android.widget.EditText"]',
        ], timeout=0.8)
        if field:
            try:
                field.click()
                return
            except Exception:
                pass

        try:
            info = self.device.info
            width  = info.get("displayWidth",  576)
            height = info.get("displayHeight", 1280)
        except Exception:
            width, height = 576, 1280

        tap_x = width  // 2
        tap_y = int(height * _WEBVIEW_INPUT_Y_RATIO)
        self.logger.debug(f"WebView tap at ({tap_x}, {tap_y}) — screen {width}×{height}")
        self.device.click(tap_x, tap_y)

    # ──────────────────────────────────────────────────────────────────
    # uiautomator2 helpers (same pattern as other workflows)
    # ──────────────────────────────────────────────────────────────────

    def _find_element(self, selectors: list, timeout: float = _EXIST_TIMEOUT):
        """Try each XPath selector and return the first matching element."""
        for xpath in selectors:
            try:
                el = self.device.xpath(xpath)
                if el.wait(timeout=timeout):
                    return el
            except Exception:
                continue
        return None

    def _click_selector(self, selectors: list, timeout: float = _EXIST_TIMEOUT) -> bool:
        el = self._find_element(selectors, timeout)
        if el:
            el.click()
            return True
        return False

    def _element_exists(self, selectors: list, timeout: float = _EXIST_TIMEOUT) -> bool:
        return self._find_element(selectors, timeout=timeout) is not None

    def _error(self, error_type: str, message: str) -> dict:
        _ipc.log("error", f"❌ {message}")
        return {
            "success":    False,
            "code":       None,
            "message":    message,
            "error_type": error_type,
        }
