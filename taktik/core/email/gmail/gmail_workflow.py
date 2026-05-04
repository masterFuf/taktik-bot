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
                            closed = self._click_selector(GMAIL_SWITCHER_SELECTORS.close, timeout=0.8)
                            if not closed:
                                self.device.press("back")
                            time.sleep(0.5)
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
            # Strategy (fast -> slow):
            #   1. Read code directly from inbox list-view content-desc - no search needed.
            #      On Samsung Gmail the email snippet is in content-desc of each
            #      conversation row, e.g.: "Non lue TikTok, 890830 est ton code TikTok..."
            #   2. Fall back to full search + open email if not found in list.
            search_query = self._build_search_query(sender_filter, subject_filter)
            deadline = time.time() + timeout

            while time.time() < deadline:
                # Fast path: read OTP from current inbox dump
                try:
                    inbox_xml = self.device.dump_hierarchy()
                    code = self._read_otp_from_inbox_dump(inbox_xml, sender_filter)
                    if code:
                        _ipc.log("info", f"✅ Verification code found in inbox: {code}")
                        return {
                            "success": True,
                            "code": code,
                            "message": f"Code found: {code}",
                            "error_type": None,
                        }
                except Exception:
                    pass

                # Slow path: search + open email
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

    def scan_accounts(self) -> dict:
        """
        Scan Gmail and return all Google accounts currently configured in the app.

        Algorithm:
          1. Open Gmail → read the active account email from the inbox header.
          2. Open the account switcher → read all listed accounts (name + email).
          3. Close the switcher.
          4. Return {"success": True, "accounts": [{name, email, is_active}], "message": "N account(s) found"}.

        The active account is shown in the switcher greeting but NOT in the
        og_secondary_account_information RecyclerView — it is inserted manually
        using the email from step 1 and the greeting display name.
        """
        self.logger.info("🔍 Scanning Gmail accounts…")
        _ipc.status("running", "Opening Gmail…")

        try:
            # ── Open Gmail ──────────────────────────────────────────────────
            _ipc.log("info", "📱 Opening Gmail…")
            self.device.app_start(_GMAIL_PACKAGE)

            # Wait for Gmail inbox — slow devices can take 15–30 s to load.
            # Poll _detect_add_account_screen() instead of a fixed sleep.
            _ipc.log("info", "⏳ Waiting for Gmail to load…")
            deadline = time.time() + 30
            while time.time() < deadline:
                screen = self._detect_add_account_screen()
                if screen in ("inbox", "switcher"):
                    _ipc.log("info", "✅ Gmail ready")
                    break
                time.sleep(1.5)
            else:
                _ipc.log("warning", "⚠️ Gmail inbox not ready after 30 s — attempting scan anyway")

            # ── Read active account email from inbox ────────────────────────
            _ipc.log("info", "🔎 Reading active account…")
            active_email = self._get_active_account_from_dump()
            _ipc.log("info", f"📧 Active account: {active_email or 'unknown'}")

            # ── Open account switcher ───────────────────────────────────────
            _ipc.log("info", "👆 Opening account switcher…")
            if not self._open_account_switcher():
                accounts = []
                if active_email:
                    accounts.append({"name": None, "email": active_email, "is_active": True})
                _ipc.log("warning", "⚠️ Switcher could not be opened — returning active account only")
                return {
                    "success": True,
                    "accounts": accounts,
                    "message": "Switcher could not be opened, only active account retrieved",
                }

            time.sleep(0.6)

            # ── Parse all accounts from switcher ────────────────────────────
            _ipc.log("info", "📋 Parsing account list…")
            accounts = self._extract_accounts_from_switcher(active_email)

            # ── Close switcher ──────────────────────────────────────────────
            self._dismiss_switcher()

            _ipc.log("info", f"✅ Found {len(accounts)} Gmail account(s)")
            _ipc.status("success", f"{len(accounts)} account(s) found")
            return {
                "success": True,
                "accounts": accounts,
                "message": f"{len(accounts)} account(s) found",
            }

        except Exception as exc:
            self.logger.exception("💥 Gmail scan_accounts failed")
            _ipc.log("error", f"❌ Gmail scan error: {exc}")
            return {"success": False, "accounts": [], "message": str(exc), "error_type": "exception"}

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
                "og_bento_selected_account_greeting_message" in h or
                "og_dialog_fragment_account_menu" in h or
                "og_popover" in h):
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
            self._dismiss_switcher()
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

    def _dismiss_switcher(self) -> None:
        """
        Dismiss the Gmail account switcher overlay.

        Strategy (most reliable → least reliable):
          1. Tap below the popup (outside its bounds) — the og_dialog /
             og_popover variant has no close button but dismisses on outside tap.
             Observed on SM-J600FN: popup bottom = y≈1024, screen height=1416,
             so tapping at y≈1200 (well below popup, well above nav bar) works.
          2. Click the visible close / back button if one is accessible.
          3. Press BACK as last resort.

        After dismissal wait 0.6 s for the animation to finish.
        """
        try:
            info = self.device.info
            width  = int(info.get("displayWidth",  656))
            height = int(info.get("displayHeight", 1416))
        except Exception:
            width, height = 656, 1416

        # Try to read the popup bottom boundary from the hierarchy
        popup_bottom = None
        try:
            h = self.device.dump_hierarchy()
            import re as _re
            # og_popover bounds e.g. "[32,182][656,1024]"
            m = _re.search(r'og_popover[^>]*bounds="\[[\d,]+\]\[(\d+),(\d+)\]"', h)
            if not m:
                m = _re.search(r'og_dialog_fragment_account_menu[^>]*bounds="\[[\d,]+\]\[(\d+),(\d+)\]"', h)
            if m:
                popup_bottom = int(m.group(2))
        except Exception:
            pass

        if popup_bottom is not None:
            # Tap 20% of the remaining screen height below the popup
            tap_y = popup_bottom + int((height - popup_bottom) * 0.4)
            tap_x = width // 2
            self.logger.debug(f"Dismissing switcher: tap outside popup at ({tap_x}, {tap_y}) "
                              f"[popup_bottom={popup_bottom}, screen_height={height}]")
            try:
                self.device.click(tap_x, tap_y)
                time.sleep(0.6)
                if not self._is_switcher_open():
                    return
            except Exception:
                pass

        # Fallback 2: close button
        if self._click_selector(GMAIL_SWITCHER_SELECTORS.close, timeout=1.0):
            time.sleep(0.6)
            if not self._is_switcher_open():
                return

        # Fallback 3: BACK key
        self.device.press("back")
        time.sleep(0.6)

    def _is_switcher_open(self) -> bool:
        """Fast check for the Gmail account switcher overlay (bento or GMS picker)."""
        try:
            h = self.device.dump_hierarchy()
        except Exception:
            return False
        hl = h.lower()
        return (
            # Gmail bento panel (com.google.android.gm)
            "og_bento_account_menu_title_text" in h
            or "og_bento_selected_account_greeting_message" in h
            # og_dialog variant (com.google.android.gm — newer Gmail builds)
            or "com.google.android.gm:id/og_dialog_view" in h
            or "com.google.android.gm:id/account_management" in h
            or "com.google.android.gm:id/og_dialog_fragment_account_menu" in h
            or "com.google.android.gm:id/og_popover" in h
            # GMS account picker (com.google.android.gms)
            or "com.google.android.gms:id/selected_account_container" in h
            or "com.google.android.gms:id/account_picker_container" in h
            # Text-based fallbacks (both panels)
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
            # Variant 1: bento panel uses og_secondary_account_information
            # Variant 2: og_dialog uses account_name (observed 2026-05-04)
            rows = []
            for row_xpath in (
                '//*[@resource-id="com.google.android.gm:id/og_secondary_account_information"]',
                '//*[@resource-id="com.google.android.gm:id/account_name"]',
            ):
                found = self.device.xpath(row_xpath).all()
                if found:
                    rows = found
                    break
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
            self._dismiss_switcher()
            time.sleep(1.0)  # wait for popup to fully dismiss before inbox dump
            return {"success": True, "message": "Correct account active", "error_type": None}

        # Account not found in switcher at all
        self._dismiss_switcher()
        time.sleep(0.5)
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
            # Check both known marker variants:
            #   selected_account_disc_gmail  — standard Gmail bento panel
            #   identity_disc_menu_item      — Samsung/og_dialog Gmail variant
            for marker in ("selected_account_disc_gmail", "identity_disc_menu_item"):
                idx = h.find(marker)
                if idx == -1:
                    continue
                node_str = h[idx: idx + 400]
                m = re.search(r'content-desc="([^"]+)"', node_str)
                if m:
                    email_match = re.search(r'[\w.+\-]+@[\w.+\-]+\.\w+', m.group(1))
                    if email_match:
                        return email_match.group(0).lower()
        except Exception:
            pass
        return None

    def _extract_accounts_from_switcher(self, active_email: Optional[str]) -> list:
        """
        Parse the currently open account switcher hierarchy and return a list
        of all configured Gmail accounts.

        Tries three known-variant parsers in order, then falls back to a
        universal regex scan of the whole hierarchy dump.  The fallback ensures
        compatibility with future or manufacturer-specific Gmail UIs that don't
        match any of the known resource-ID patterns.

        Known variants:
          1. Gmail bento panel   — og_bento_* / og_primary/secondary_account_information
          2. og_dialog variant   — og_dialog_view / account_management RecyclerView
          3. GMS account picker  — com.google.android.gms:id/selected_account_*
          4. Regex fallback      — emails extracted from text= / content-desc= attributes
        """
        accounts: list = []
        active_email_norm = (active_email or "").lower()

        try:
            h = self.device.dump_hierarchy()
        except Exception as exc:
            self.logger.debug(f"Could not dump hierarchy: {exc}")
            return accounts

        is_bento     = "og_bento_selected_account_greeting_message" in h or "og_primary_account_information" in h
        is_og_dialog = not is_bento and (
            "com.google.android.gm:id/og_dialog_view" in h
            or "com.google.android.gm:id/account_management" in h
        )
        is_gms       = "com.google.android.gms:id/selected_account_container" in h

        if is_bento:
            # ── Gmail bento: other accounts via og_primary/secondary rows ──
            try:
                email_nodes = self.device.xpath(
                    '//*[@resource-id="com.google.android.gm:id/og_secondary_account_information"]'
                ).all()
                name_nodes = self.device.xpath(
                    '//*[@resource-id="com.google.android.gm:id/og_primary_account_information"]'
                ).all()
                for i, email_node in enumerate(email_nodes):
                    email_text = (email_node.info.get("text") or "").strip()
                    name_text = (name_nodes[i].info.get("text") or "").strip() if i < len(name_nodes) else None
                    if email_text:
                        accounts.append({
                            "name": name_text or None,
                            "email": email_text,
                            "is_active": email_text.lower() == active_email_norm,
                        })
            except Exception as exc:
                self.logger.debug(f"Could not parse Gmail bento account rows: {exc}")

            # Active account (greeting header) not in the secondary rows
            if active_email_norm and not any(
                a["email"].lower() == active_email_norm for a in accounts
            ):
                active_name = self._get_active_account_name_from_switcher_bento(h)
                accounts.insert(0, {
                    "name": active_name,
                    "email": active_email,
                    "is_active": True,
                })
            else:
                for a in accounts:
                    if a["email"].lower() == active_email_norm:
                        a["is_active"] = True

        elif is_gms:
            # ── GMS account picker: parse from hierarchy string directly ──
            name_m  = re.search(r'selected_account_name[^/]*text="([^"]+)"', h)
            email_m = re.search(r'selected_account_email[^/]*text="([^"]+)"', h)
            if email_m:
                sel_email = email_m.group(1).strip()
                sel_name  = name_m.group(1).strip() if name_m else None
                if sel_email:
                    accounts.append({
                        "name": sel_name or None,
                        "email": sel_email,
                        "is_active": True,
                    })
                    if not active_email_norm:
                        active_email_norm = sel_email.lower()

            # Additional accounts (extra rows) — look for gms account_email/name IDs
            try:
                extra_email_nodes = self.device.xpath(
                    '//*[@resource-id="com.google.android.gms:id/account_email"]'
                ).all()
                extra_name_nodes = self.device.xpath(
                    '//*[@resource-id="com.google.android.gms:id/account_name"]'
                ).all()
                for i, en in enumerate(extra_email_nodes):
                    et = (en.info.get("text") or "").strip()
                    nt = (extra_name_nodes[i].info.get("text") or "").strip() if i < len(extra_name_nodes) else None
                    if et and et.lower() != active_email_norm:
                        accounts.append({"name": nt or None, "email": et, "is_active": False})
            except Exception as exc:
                self.logger.debug(f"Could not read GMS extra account rows: {exc}")

        elif is_og_dialog:
            # ── og_dialog variant: account_display_name nodes in hierarchy ──
            # Structure: selected_account_view (active) + account_management
            # RecyclerView (others). All use account_display_name for the email.
            # The active account's display_name is the FIRST match in the dump.
            try:
                email_matches = re.findall(
                    r'account_display_name[^/]*?text="([^"]+)"', h
                )
                for i, email_text in enumerate(email_matches):
                    email_text = email_text.strip()
                    if not email_text:
                        continue
                    is_active = (
                        email_text.lower() == active_email_norm
                        if active_email_norm
                        else i == 0
                    )
                    accounts.append({
                        "name": None,
                        "email": email_text,
                        "is_active": is_active,
                    })
            except Exception as exc:
                self.logger.debug(f"Could not parse og_dialog account rows: {exc}")

        # ── Universal regex fallback ──────────────────────────────────────────
        # If no specific parser matched or all parsers returned empty, extract
        # emails directly from the hierarchy dump.  Works on any Gmail UI variant
        # as long as accounts are visible as text= or content-desc= attributes.
        if not accounts:
            self.logger.debug(
                f"Specific Gmail switcher parser returned 0 accounts "
                f"(bento={is_bento}, og_dialog={is_og_dialog}, gms={is_gms}) "
                f"— using regex fallback"
            )
            accounts = self._extract_emails_from_hierarchy(h, active_email_norm, active_email)

        return accounts

    def _extract_emails_from_hierarchy(
        self,
        h: str,
        active_email_norm: str,
        active_email: Optional[str],
    ) -> list:
        """
        Universal fallback: scan the full hierarchy dump for email addresses.

        Extracts from:
          - content-desc= attributes (contains "Connecté en tant que X" / "Use X" / etc.)
          - text= attributes (account_display_name, plain email rows)

        Determines the active account via:
          1. active_email_norm if provided
          2. Content-desc patterns like "connecté en tant que" / "connected as"
          3. First email found (last resort)
        """
        EMAIL_RE = re.compile(r'[\w.+\-]+@[\w.\-]+\.[a-z]{2,}', re.IGNORECASE)
        seen: dict = {}  # lower_email -> entry dict  (preserves insertion order)

        # ── Pass 1: content-desc attributes (reliable for active/inactive) ──
        for m in re.finditer(r'content-desc="([^"]*)"', h):
            desc = m.group(1)
            desc_l = desc.lower()
            for email in EMAIL_RE.findall(desc):
                key = email.lower()
                if key in seen:
                    continue
                # Heuristic: "connecté en tant que" / "connected as" → active
                is_active = (
                    key == active_email_norm
                    if active_email_norm
                    else (
                        "connecté en tant que" in desc_l
                        or "connected as" in desc_l
                        or "signed in as" in desc_l
                        or "ouvrir le menu des comptes" in desc_l
                        or "open account menu" in desc_l
                    )
                )
                seen[key] = {"name": None, "email": email, "is_active": is_active}

        # ── Pass 2: text= attributes (account rows, display name fields) ──
        for m in re.finditer(r'\btext="([^"]*@[^"]*)"', h):
            val = m.group(1).strip()
            for email in EMAIL_RE.findall(val):
                key = email.lower()
                if key in seen:
                    continue
                seen[key] = {
                    "name": None,
                    "email": email,
                    "is_active": key == active_email_norm if active_email_norm else False,
                }

        # ── Ensure active_email appears even if it wasn't in the dump ──
        if active_email and active_email_norm not in seen:
            seen[active_email_norm] = {"name": None, "email": active_email, "is_active": True}
            # Move it to the front
            seen = {active_email_norm: seen[active_email_norm], **seen}

        accounts = list(seen.values())

        # ── Last resort: if nothing is marked active, mark the first entry ──
        if accounts and not any(a["is_active"] for a in accounts):
            accounts[0]["is_active"] = True

        return accounts

    def _get_active_account_name_from_switcher(self) -> Optional[str]:
        """
        Extract the display name of the active account from whatever switcher
        is currently open.

        Tries:
          1. Gmail bento greeting (og_bento_selected_account_greeting_message)
          2. GMS picker selected_account_name
        """
        try:
            h = self.device.dump_hierarchy()
        except Exception:
            return None
        name = self._get_active_account_name_from_switcher_bento(h)
        if name:
            return name
        # GMS picker fallback
        try:
            m = re.search(
                r'selected_account_name[^>]*text="([^"]+)"', h
            )
            if m:
                return m.group(1).strip() or None
        except Exception:
            pass
        return None

    def _get_active_account_name_from_switcher_bento(self, h: str) -> Optional[str]:
        """
        Extract the display name from the Gmail bento greeting element.

        The greeting element (og_bento_selected_account_greeting_message) contains:
          - FR: "Bonjour <name> !"
          - EN: "Hi, <name>!"
        Returns the extracted name, or None if it cannot be determined.
        """
        try:
            idx = h.find("og_bento_selected_account_greeting_message")
            if idx == -1:
                return None
            snippet = h[idx: idx + 200]
            m = re.search(r'text="([^"]+)"', snippet)
            if m:
                greeting = m.group(1)
                for prefix in ("Bonjour ", "Hi, "):
                    if greeting.startswith(prefix):
                        name = greeting[len(prefix):].rstrip(" !").strip()
                        if name:
                            return name
                return greeting.strip()
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

        Searches all `text` AND `content-desc` attribute values.
        On Samsung Gmail, email snippets are in content-desc, not text.
        Returns the first match, or None.
        """
        patterns = [
            r'\b(\d{6})\b',
            r'code\s*[:\-–]\s*(\d{6})',
            r'code\s+is\s+(\d{6})',
            r'code\s+est\s*[:\-–]?\s*(\d{6})',
        ]
        # Search both text= and content-desc= attribute values
        values = re.findall(r'(?:text|content-desc)="([^"]+)"', hierarchy_xml)
        for value in values:
            for pattern in patterns:
                match = re.search(pattern, value, re.IGNORECASE)
                if match:
                    return match.group(1)
        # Fallback: scan entire XML for any standalone 6-digit sequence
        match = re.search(r'\b(\d{6})\b', hierarchy_xml)
        if match:
            return match.group(1)
        return None

    def _read_otp_from_inbox_dump(
        self,
        hierarchy_xml: str,
        sender_filter: Optional[str] = None,
    ) -> Optional[str]:
        """
        Extract a 6-digit OTP from the Gmail inbox list-view dump WITHOUT
        opening the email.

        On Samsung Gmail each conversation row exposes its full subject + preview
        in content-desc, e.g.:
          "Non lue TikTok, 890830 est ton code TikTok, Verifie..."

        If sender_filter is given (e.g. "TikTok"), only rows whose
        content-desc contains that string (case-insensitive) are examined.
        """
        patterns = [
            r'\b(\d{6})\b',
            r'code\s*[:\-–]\s*(\d{6})',
            r'code\s+is\s+(\d{6})',
            r'code\s+est\s*[:\-–]?\s*(\d{6})',
        ]
        descs = re.findall(r'content-desc="([^"]+)"', hierarchy_xml)
        for desc in descs:
            if sender_filter and sender_filter.lower() not in desc.lower():
                continue
            for pattern in patterns:
                m = re.search(pattern, desc, re.IGNORECASE)
                if m:
                    return m.group(1)
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
