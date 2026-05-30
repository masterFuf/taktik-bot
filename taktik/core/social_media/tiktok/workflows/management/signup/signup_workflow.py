"""
TikTok Signup Workflow

Handles the registration of a new TikTok account on a device.

Architecture : state machine (screen-detection loop)
  Rather than assuming a fixed step sequence, the workflow detects which
  screen is currently displayed and acts accordingly.  This handles the fact
  that TikTok can insert screens in different orders depending on the app
  state (fresh install, region, language…).

Known screens and transitions :
  BIRTHDAY_GATE   – pre-inscription birthday forced by TikTok on first open
                    → click "Inscription" link at bottom (id=mfb)
                    → next: SIGNUP_POPUP
  SIGNUP_POPUP    – "Inscription à TikTok" modal
                    → click "Utiliser un numéro de téléphone ou une adresse e-mail"
                    → next: BIRTHDAY_SIGNUP  (or directly PHONE_EMAIL on some versions)
  BIRTHDAY_SIGNUP – birthday inside signup flow (no "Inscription" link at bottom)
                    → fill day/month/year, click Continuer
                    → next: PHONE_EMAIL
  PHONE_EMAIL     – phone + email tabs + input field
                    → select correct tab, fill, click Continuer
                    → next: OTP / password  (TODO with next dumps)
"""
import time
from typing import Optional

from loguru import logger
from bridges.common.ipc import IPC
from taktik.core.social_media.tiktok.ui.selectors.shell.auth import (
    SIGNUP_SELECTORS,
    COUNTRY_PICKER_SELECTORS,
    TIKTOK_PACKAGE,
)
from taktik.core.email.gmail.gmail_workflow import GmailWorkflow

_ipc = IPC()

# ── State machine constants ─────────────────────────────────────────────────

# Maximum state-machine iterations before giving up
_MAX_ITERATIONS = 20
# Pause between state-machine iterations (seconds)
_ITER_PAUSE = 0.5
# Timeout for quick element-existence checks (seconds)
_EXIST_TIMEOUT = 0.4

# ── Birthday picker constants ───────────────────────────────────────────────

# Max rows (items) to scroll per single swipe gesture when far from target.
# Clamped by max_dist (~184px for a 200px picker) — no real benefit beyond 3.
_PICKER_ROWS_PER_SWIPE = 3
# Max swipe attempts per picker field before giving up
_PICKER_MAX_ATTEMPTS = 60
# Swipe gesture duration (seconds).
# 0.12s was too short → Android registers it as a fling and the picker jumps
# unpredictably.  0.22s is fast & human-like while staying below inertia threshold.
_PICKER_SWIPE_DURATION = 0.22
# Settling pause after the final (1-row) swipe before re-reading the value
_PICKER_SETTLE = 0.30

# Month-name → month-number (French + English, abbreviated + full)
_MONTH_NAMES: dict = {
    'jan': 1, 'janv': 1, 'janvier': 1, 'january': 1,
    'fév': 2, 'févr': 2, 'février': 2, 'feb': 2, 'february': 2,
    'mar': 3, 'mars': 3, 'march': 3,
    'avr': 4, 'avril': 4, 'apr': 4, 'april': 4,
    'mai': 5, 'may': 5,
    'juin': 6, 'jun': 6, 'june': 6,
    'juil': 7, 'jul': 7, 'july': 7, 'juillet': 7,
    'août': 8, 'aou': 8, 'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'septembre': 9, 'september': 9,
    'oct': 10, 'octobre': 10, 'october': 10,
    'nov': 11, 'novembre': 11, 'november': 11,
    'déc': 12, 'dec': 12, 'décembre': 12, 'december': 12,
}


class TikTokSignupWorkflow:
    """Workflow for registering a new TikTok account on a connected Android device."""

    def __init__(self, device, device_id: str):
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(device=device_id)

    # ------------------------------------------------------------------
    # Public entry-point – state machine
    # ------------------------------------------------------------------

    def execute(
        self,
        method: str = "email",
        email: Optional[str] = None,
        phone: Optional[str] = None,
        phone_country: Optional[str] = None,
        birth_year: int = 1995,
        birth_month: int = 6,
        birth_day: int = 15,
        gmail_password: Optional[str] = None,
        tiktok_password: Optional[str] = None,
        nickname: Optional[str] = None,
    ) -> dict:
        """
        Execute the TikTok signup workflow using screen-detection.

        The method detects the current screen on each iteration and takes the
        appropriate action, rather than following a hardcoded sequential path.

        Args:
            method:         "email" or "phone"
            email:          Email address (required if method="email")
            phone:          Phone number (required if method="phone")
            phone_country:  Country name for phone code picker (e.g. "France").
                            If None, the default country shown by TikTok is used.
            birth_year:     Year of birth (default 1995)
            birth_month:    Month 1-12 (default 6)
            birth_day:      Day 1-31 (default 15)
            gmail_password: Gmail password for OTP retrieval via Gmail app.
                            Required when method="email" and the email is a Gmail
                            address. If omitted the OTP step will need manual input.
            tiktok_password: Password for the new TikTok account.
                            Must be 8–20 chars with ≥1 letter, ≥1 digit, ≥1 special
                            char from #?!@.  If None, a random valid password is
                            generated automatically.
            nickname:       TikTok username (surnom) for the new account.
                            If None the nickname screen is skipped ("Ignorer").

        Returns:
            dict: {success, step, message, error_type}
        """
        self.logger.info(f"📝 TikTok signup — method={method}")
        _ipc.status("running", f"Starting registration ({method})...")

        birthday_done = False
        birthday_transition_retries = 0
        _MAX_BIRTHDAY_TRANSITION = 5   # up to ~15 s for Samsung to leave the birthday screen
        _BIRTHDAY_TRANSITION_WAIT = 3.0
        email_submitted = False
        email_transition_retries = 0
        _MAX_EMAIL_TRANSITION = 5      # up to ~15 s for Samsung to leave the email screen
        _EMAIL_TRANSITION_WAIT = 3.0
        otp_done = False
        password_done = False
        nickname_done = False
        unknown_retries = 0
        _MAX_UNKNOWN_RETRIES = 4   # wait up to ~12 s on loading/unknown screens
        _UNKNOWN_WAIT = 3.0        # seconds to wait between unknown retries

        try:
            for iteration in range(_MAX_ITERATIONS):
                screen = self._detect_screen()
                _ipc.log("info", f"🔍 Screen [{iteration+1}/{_MAX_ITERATIONS}]: {screen}")
                self.logger.debug(f"Signup state machine — iteration={iteration+1} screen={screen}")

                if screen != "unknown":
                    unknown_retries = 0

                # ── GDPR POPUP ───────────────────────────────────────────
                if screen == "gdpr_popup":
                    _ipc.log("info", "📋 GDPR popup detected — dismissing...")
                    if not self._click_selector(SIGNUP_SELECTORS.gdpr_got_it_button, timeout=5.0):
                        return self._error("gdpr_got_it_not_found",
                                           "Could not click 'Got it' on GDPR popup")
                    time.sleep(_ITER_PAUSE)
                    # If signup steps are all done, the popup was the last obstacle
                    if nickname_done:
                        _ipc.log("info", "✅ Registration complete!")
                        return {"success": True, "step": "complete",
                                "message": "TikTok registration complete",
                                "error_type": None}

                # ── BIRTHDAY_GATE ────────────────────────────────────────
                elif screen == "birthday_gate":
                    # Click the "Inscription" link at the bottom of the screen
                    if not self._click_selector(SIGNUP_SELECTORS.birthday_gate_inscription_link, timeout=4.0):
                        return self._error("birthday_gate_inscription_not_found",
                                           "Could not click 'Inscription' on birthday gate screen")
                    time.sleep(_ITER_PAUSE)

                # ── SIGNUP_POPUP ─────────────────────────────────────────
                elif screen == "signup_popup":
                    # Click "Utiliser un numéro de téléphone ou une adresse e-mail"
                    if not self._click_selector(SIGNUP_SELECTORS.use_phone_or_email_button, timeout=5.0):
                        return self._error("use_phone_email_not_found",
                                           "Could not click 'Use phone or email' on signup popup")
                    time.sleep(_ITER_PAUSE)

                # ── BIRTHDAY_SIGNUP ──────────────────────────────────────
                elif screen == "birthday_signup":
                    if birthday_done:
                        # Birthday screen still visible after "Continuer" was clicked —
                        # Samsung transitions can be slow; wait and retry.
                        birthday_transition_retries += 1
                        if birthday_transition_retries >= _MAX_BIRTHDAY_TRANSITION:
                            return self._error("birthday_loop",
                                               f"Birthday screen still visible after {birthday_transition_retries} retries")
                        _ipc.log("info", f"⏳ Waiting for transition after birthday ({birthday_transition_retries}/{_MAX_BIRTHDAY_TRANSITION})...")
                        time.sleep(_BIRTHDAY_TRANSITION_WAIT)
                        continue
                    _ipc.log("info", "🎂 Filling date of birth...")
                    result = self._fill_birthday(birth_day, birth_month, birth_year)
                    if not result["success"]:
                        return result
                    birthday_done = True
                    time.sleep(_ITER_PAUSE)

                # ── PHONE_EMAIL ──────────────────────────────────────────
                elif screen == "phone_email":
                    if email_submitted:
                        # Email screen still visible after "Continuer" was clicked —
                        # Samsung transitions can be slow; wait and retry.
                        email_transition_retries += 1
                        if email_transition_retries >= _MAX_EMAIL_TRANSITION:
                            return self._error("phone_email_loop",
                                               f"Phone/email screen still visible after {email_transition_retries} retries")
                        _ipc.log("info", f"⏳ Waiting for transition after email submission ({email_transition_retries}/{_MAX_EMAIL_TRANSITION})...")
                        time.sleep(_EMAIL_TRANSITION_WAIT)
                        continue
                    _ipc.log("info", f"✏️  Filling {method} registration details...")
                    result = self._handle_phone_email(method, email, phone, phone_country)
                    if not result["success"]:
                        return result
                    email_submitted = True
                    time.sleep(_ITER_PAUSE)

                # ── OTP (verification code entry) ────────────────────────
                elif screen == "otp_entry":
                    if otp_done:
                        # OTP screen still visible after code entry — wait for transition
                        unknown_retries += 1
                        if unknown_retries >= _MAX_UNKNOWN_RETRIES:
                            return self._error("otp_loop", "OTP screen still visible after code entry")
                        time.sleep(_UNKNOWN_WAIT)
                        continue
                    _ipc.log("info", "\U0001f511 OTP screen detected \u2014 retrieving verification code...")
                    result = self._handle_otp(method, email, gmail_password)
                    if not result["success"]:
                        return result
                    otp_done = True
                    unknown_retries = 0
                    time.sleep(_ITER_PAUSE)

                # ── PASSWORD ───────────────────────────────────
                elif screen == "password_entry":
                    _ipc.log("info", "\U0001f510 Password screen detected — setting password...")
                    result = self._handle_password(tiktok_password)
                    if not result["success"]:
                        return result
                    password_done = True
                    unknown_retries = 0
                    time.sleep(_ITER_PAUSE)

                # ── NICKNAME ──────────────────────────────────
                elif screen == "nickname_entry":
                    _ipc.log("info", "\U0001f4db Nickname screen detected — setting username...")
                    result = self._handle_nickname(nickname)
                    if not result["success"]:
                        return result
                    nickname_done = True
                    unknown_retries = 0
                    time.sleep(_ITER_PAUSE)

                # ── UNKNOWN ──────────────────────────────────────────────
                else:
                    # If nickname step is done, unknown = TikTok home → success
                    if nickname_done:
                        _ipc.log("info", "\u2705 Registration complete!")
                        return {"success": True, "step": "complete",
                                "message": "TikTok registration complete",
                                "error_type": None}
                    unknown_retries += 1
                    if unknown_retries >= _MAX_UNKNOWN_RETRIES:
                        # Dump the hierarchy once for debugging before giving up
                        try:
                            xml = self.device.dump_hierarchy(compressed=False)
                            self.logger.debug(f"UI dump on unknown screen:\n{xml[:4000]}")
                        except Exception:
                            pass
                        return self._error(
                            "unknown_screen",
                            f"Unrecognised screen after {unknown_retries} retries "
                            f"(iteration {iteration+1}). Check device logs.",
                        )
                    _ipc.log("info", f"⏳ Unknown screen — waiting {_UNKNOWN_WAIT}s (retry {unknown_retries}/{_MAX_UNKNOWN_RETRIES})...")
                    time.sleep(_UNKNOWN_WAIT)
                    continue

            return self._error("max_iterations",
                               f"Signup did not complete after {_MAX_ITERATIONS} iterations")

        except Exception as exc:
            self.logger.exception("💥 TikTok signup failed")
            _ipc.log("error", f"❌ Signup error: {exc}")
            return {"success": False, "step": "exception", "message": str(exc), "error_type": "exception"}

    # ------------------------------------------------------------------
    # Private helpers – screen detection
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
        return {"success": False, "step": error_type, "message": message, "error_type": error_type}

    def _element_exists(self, selectors: list, timeout: float = _EXIST_TIMEOUT) -> bool:
        """Return True if any of the XPath selectors matches within *timeout* seconds."""
        return self._find_element(selectors, timeout=timeout) is not None

    def _detect_screen(self) -> str:
        """
        Detect the current screen state in a single hierarchy dump.

        Performance: instead of polling each XPath with a 2s timeout (which
        on an unknown screen would cost ~40s — sum of all selectors), we dump
        the UI hierarchy once and run every XPath against the parsed tree.
        Typical cost: ~0.5s per detection regardless of outcome.

        Priority order ensures unambiguous detection:
          1. BIRTHDAY_GATE  – birthday + "Inscription" link (id=mfb)  ← most specific
          2. BIRTHDAY_SIGNUP – birthday pickers, no mfb link
             (checked BEFORE signup_popup to prevent generic title selectors
              from falsely matching the birthday screen)
          3. SIGNUP_POPUP  – "Inscription à TikTok" modal
          4. OTP_ENTRY     – OTP verification code input screen
          5. PHONE_EMAIL   – phone/email input field

        XPath translation:
          uiautomator2's dump_hierarchy returns XML where every element has
          the tag <node> with a "class" attribute — NOT tag names like
          <android.widget.EditText>.  Selectors written in the uiautomator2
          convention (e.g. //android.widget.EditText[@hint="x"]) must be
          rewritten for lxml as //node[@class="android.widget.EditText"][@hint="x"].
          _to_lxml() does this automatically so all existing selectors work.
        """
        import re as _re
        from lxml import etree  # local import; lxml ships with uiautomator2

        # Matches a dotted Java class name used as an XPath element step,
        # preceded by one or two slashes.
        # e.g. //android.widget.EditText  →  //node[@class="android.widget.EditText"]
        _CLASS_STEP_RE = _re.compile(
            r'(/{1,2})([a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*)+)'
        )

        def _to_lxml(xp: str) -> str:
            return _CLASS_STEP_RE.sub(r'\1node[@class="\2"]', xp)

        try:
            xml = self.device.dump_hierarchy(compressed=False)
            tree = etree.fromstring(xml.encode('utf-8'))
        except Exception as exc:
            self.logger.warning(f"_detect_screen: hierarchy dump failed ({exc}), falling back to slow path")
            return self._detect_screen_slow()

        def matches(selectors: list) -> bool:
            for xp in selectors:
                try:
                    if tree.xpath(_to_lxml(xp)):
                        return True
                except etree.XPathEvalError:
                    continue
            return False

        # GDPR popup: can appear at any time as an overlay — check it first
        if matches(SIGNUP_SELECTORS.gdpr_popup_indicator):
            return "gdpr_popup"
        # Birthday gate first: has unique "mfb" button — unambiguous, fastest to discard
        if matches(SIGNUP_SELECTORS.birthday_gate_inscription_link):
            return "birthday_gate"
        # Birthday signup BEFORE signup_popup: the SeekBar pickers / birthday text
        # are specific; checking here prevents generic signup_popup selectors
        # (e.g. title text) from falsely matching the birthday screen.
        if matches(SIGNUP_SELECTORS.birthday_screen_indicator):
            return "birthday_signup"
        if matches(SIGNUP_SELECTORS.signup_popup_indicator):
            return "signup_popup"
        # OTP must be checked BEFORE phone_email: the OTP screen has 6 EditText
        # boxes (digit inputs) which would otherwise match email_input/phone_input.
        if matches(SIGNUP_SELECTORS.otp_screen_indicator):
            return "otp_entry"
        if matches(SIGNUP_SELECTORS.password_entry_indicator):
            return "password_entry"
        if matches(SIGNUP_SELECTORS.nickname_entry_indicator):
            return "nickname_entry"
        if matches(SIGNUP_SELECTORS.phone_input) or matches(SIGNUP_SELECTORS.email_input):
            return "phone_email"
        return "unknown"

    def _detect_screen_slow(self) -> str:
        """Fallback to per-xpath polling (used only if dump_hierarchy fails)."""
        # GDPR popup: can appear at any time as an overlay — check it first
        if self._element_exists(SIGNUP_SELECTORS.gdpr_popup_indicator):
            return "gdpr_popup"
        if self._element_exists(SIGNUP_SELECTORS.birthday_gate_inscription_link):
            return "birthday_gate"
        if self._element_exists(SIGNUP_SELECTORS.birthday_screen_indicator):
            return "birthday_signup"
        if self._element_exists(SIGNUP_SELECTORS.signup_popup_indicator):
            return "signup_popup"
        # OTP must be checked BEFORE phone_email — the OTP screen has 6 EditText
        # digit boxes which would otherwise match the phone_input/email_input selectors.
        if self._element_exists(SIGNUP_SELECTORS.otp_screen_indicator):
            return "otp_entry"
        if self._element_exists(SIGNUP_SELECTORS.password_entry_indicator):
            return "password_entry"
        if self._element_exists(SIGNUP_SELECTORS.nickname_entry_indicator):
            return "nickname_entry"
        if (self._element_exists(SIGNUP_SELECTORS.phone_input) or
                self._element_exists(SIGNUP_SELECTORS.email_input)):
            return "phone_email"
        return "unknown"

    # ── Step helpers ────────────────────────────────────────────────────

    def _fill_birthday(self, day: int, month: int, year: int) -> dict:
        """
        Fill the birthday scroll pickers using a feedback loop.

        Strategy:
          1. Find the three SeekBar pickers and the live-summary EditText.
          2. For each field (day, month, year): read current value from the
             EditText, calculate delta, swipe the picker in small increments,
             re-read after each swipe until the value matches (or give up).
          3. Click "Continuer".

        The EditText (id=jsh) always reflects the currently selected date,
        e.g. "10 juin 2025".  Parsing it gives us live feedback so we are
        never guessing the current picker position.
        """
        _ipc.log("info", f"📅 Setting birthday: {day:02d}/{month:02d}/{year}")

        day_el   = self._find_element(SIGNUP_SELECTORS.birthday_day_picker,   timeout=5.0)
        month_el = self._find_element(SIGNUP_SELECTORS.birthday_month_picker, timeout=5.0)
        year_el  = self._find_element(SIGNUP_SELECTORS.birthday_year_picker,  timeout=5.0)

        if not (day_el and month_el and year_el):
            return self._error("birthday_pickers_not_found",
                               "Could not find birthday date pickers")

        # Scroll each field until it shows the target value
        fields = [
            ("day",   day_el,   day,   0),
            ("month", month_el, month, 1),
            ("year",  year_el,  year,  2),
        ]
        for field_name, el, target, idx in fields:
            ok = self._scroll_picker_until(el, target, idx)
            if not ok:
                _ipc.log("warning", f"⚠️ Could not reach {field_name}={target} precisely")

        time.sleep(0.4)

        if not self._click_selector(SIGNUP_SELECTORS.birthday_continue_button, timeout=5.0):
            return self._error("birthday_continue_not_found",
                               "Could not click Continuer on birthday screen")

        _ipc.log("info", "✅ Birthday confirmed")
        return {"success": True}

    def _read_birthday(self) -> Optional[tuple]:
        """
        Read the currently displayed date from the live-summary EditText.

        Returns (day: int, month: int, year: int) or None.
        Expected format: "10 juin 2025" (FR) or "10 June 2025" (EN).
        """
        el = self._find_element(SIGNUP_SELECTORS.birthday_input, timeout=2.0)
        if not el:
            return None
        text = (el.info.get('text') or '').strip()
        placeholders = ('date de naissance', 'birthday', 'date of birth', '')
        if text.lower() in placeholders:
            return None
        return self._parse_birthday_text(text)

    def _parse_birthday_text(self, text: str) -> Optional[tuple]:
        """
        Parse "10 juin 2025" or "10 June 2025" → (day, month, year).
        Returns None if unparseable.
        """
        parts = text.strip().split()
        if len(parts) < 3:
            return None
        try:
            day   = int(parts[0])
            month = _MONTH_NAMES.get(parts[1].lower().rstrip('.'))
            year  = int(parts[2])
            if month:
                return (day, month, year)
        except (ValueError, IndexError):
            pass
        return None

    def _scroll_picker_until(self, el, target: int, field_idx: int) -> bool:
        """
        Scroll a birthday picker SeekBar until the displayed value equals *target*.

        Uses the live EditText summary as feedback after every swipe so the
        position is always known regardless of inertia or initial state.

        Critical constraint: the TikTok picker is ~200px tall (3 rows visible,
        ~66px/row). A swipe whose start or end point lies outside the element
        bounds is silently ignored by the Android touch system.  We therefore
        clamp every swipe to [top+pad, bot-pad] and derive the actual distance
        from that — typically ~184px = 2.8 rows per swipe.

        Args:
            el:        uiautomator2 element for the SeekBar to scroll.
            target:    Desired integer value (day 1-31, month 1-12, year YYYY).
            field_idx: 0=day, 1=month, 2=year (index into the parsed tuple).

        Returns True if target reached, False after max attempts.
        """
        bounds = el.info.get('bounds', {})
        cx  = (bounds['left'] + bounds['right']) // 2
        cy  = (bounds['top'] + bounds['bottom']) // 2
        row_h = (bounds['bottom'] - bounds['top']) / 3.0

        # Safe zone inside the picker — swipes must start AND end here so the
        # Android touch system registers them on the correct widget.
        pad     = 8
        top_s   = bounds['top']    + pad
        bot_s   = bounds['bottom'] - pad
        max_dist = bot_s - top_s   # ≈ 184px for a 200px-tall picker

        _prev_current: Optional[int] = None
        _null_streak  = 0          # consecutive None reads

        for attempt in range(_PICKER_MAX_ATTEMPTS):
            parsed = self._read_birthday()
            if parsed is None:
                _null_streak += 1
                # Every 3 consecutive None reads the EditText is stuck on its
                # placeholder ("Date de naissance").  The picker needs at least
                # one snap (~33px) before TikTok updates the live-feedback
                # EditText.  Use a full row-height swipe so TikTok registers the
                # scroll and populates the value.
                if _null_streak % 3 == 0:
                    wake = max(40, int(row_h))
                    yw1 = max(top_s, cy - wake // 2)
                    yw2 = min(bot_s, yw1 + wake)
                    self.device.swipe(cx, yw1, cx, yw2, duration=0.3)
                time.sleep(0.4)
                continue
            _null_streak = 0

            current = parsed[field_idx]
            if current == target:
                return True

            delta     = current - target   # >0 → need to decrease, <0 → need to increase
            abs_delta = abs(delta)

            # ── Swipe distance ──────────────────────────────────────────────
            # When only 1 row away a full row_h swipe (66px) triggers picker
            # inertia and overshoots to -2/+2, causing infinite oscillation.
            # Using ~55% of row_h (≈36px) stays below the inertia threshold
            # while still reliably crossing the ~0.5-row snap threshold.
            # Track the last reading to detect oscillation and halve further.
            if abs_delta == 1:
                base_dist = max(22, int(row_h * 0.55))
                # If we just overshot (prev was on the other side of target),
                # go even shorter to break the oscillation.
                if (attempt > 0       and
                        _prev_current is not None and
                        abs(_prev_current - target) == 1 and
                        (_prev_current - target) * delta < 0):
                    base_dist = max(16, int(base_dist * 0.65))
                dist = base_dist
            else:
                rows = min(abs_delta, _PICKER_ROWS_PER_SWIPE)
                dist = min(int(rows * row_h), max_dist)

            _prev_current = current

            if delta > 0:
                # Decrease value: drag DOWN (y increases)
                y1 = max(top_s, cy - dist // 2)
                y2 = min(bot_s, y1 + dist)
            else:
                # Increase value: drag UP (y decreases)
                y1 = min(bot_s, cy + dist // 2)
                y2 = max(top_s, y1 - dist)

            self.device.swipe(cx, y1, cx, y2, duration=_PICKER_SWIPE_DURATION)

            # Adaptive settle: fast when far from target, careful when close
            # to stop before overshooting the last row.
            if abs_delta > 5:
                time.sleep(0.08)   # far away — keep moving fast
            elif abs_delta > 1:
                time.sleep(0.20)   # getting close — slow down a bit
            else:
                time.sleep(_PICKER_SETTLE)  # last row — wait for full settle

        self.logger.warning(
            f"Picker field idx={field_idx} did not reach target={target} "
            f"after {_PICKER_MAX_ATTEMPTS} attempts"
        )
        return False

    def _handle_phone_email(
        self,
        method: str,
        email: Optional[str],
        phone: Optional[str],
        phone_country: Optional[str],
    ) -> dict:
        """
        Select the correct tab (Phone/Email) and fill the input field.
        Called when screen detection returns "phone_email".

        We use el.set_text() instead of device.send_keys() because set_text()
        goes through Android's AccessibilityNodeInfo.ACTION_SET_TEXT and does
        not require the ADB keyboard IME to be active.
        """
        # Select the correct tab first
        if method == "email":
            # Click E-mail tab (no-op if already selected)
            self._click_selector(SIGNUP_SELECTORS.tab_email, timeout=4.0)
            time.sleep(0.5)
            if not email:
                return self._error("missing_email", "Email is required for email registration")
            el = self._find_element(SIGNUP_SELECTORS.email_input, timeout=6.0)
            if not el:
                return self._error("email_input_not_found", "Email input field not found")
            el.click()
            time.sleep(0.3)
            el.set_text(email)
            time.sleep(0.3)
            _ipc.log("info", f"✅ Email entered: {email}")
        else:
            # Click Téléphone tab
            self._click_selector(SIGNUP_SELECTORS.tab_phone, timeout=4.0)
            time.sleep(0.5)
            if not phone:
                return self._error("missing_phone", "Phone number is required for phone registration")
            # Country code picker
            if phone_country:
                _ipc.log("info", f"🌍 Selecting country: {phone_country}...")
                self._select_country_code(phone_country)
                time.sleep(0.5)
            el = self._find_element(SIGNUP_SELECTORS.phone_input, timeout=6.0)
            if not el:
                return self._error("phone_input_not_found", "Phone input field not found")
            el.click()
            time.sleep(0.3)
            el.set_text(phone)
            time.sleep(0.3)
            _ipc.log("info", f"✅ Phone entered: {phone}")

        if not self._click_selector(SIGNUP_SELECTORS.continue_button, timeout=5.0):
            return self._error("continue_not_found",
                               f"Could not click Continue after {method} entry")

        return {"success": True}

    def _handle_otp(
        self,
        method: str,
        email: Optional[str],
        gmail_password: Optional[str],
    ) -> dict:
        """
        Handle the OTP verification code entry screen.

        Email OTP (method="email"):
          - If gmail_password is provided: calls ensure_account_added() to add
            the Gmail account to the device if needed, then reads the inbox.
          - If gmail_password is absent: assumes the account is already set up
            on the device (pre-configured via the Gmail tab) and goes straight
            to get_latest_verification_code().
        Phone OTP is not yet automated.

        The OTP is entered either as a single 6-digit string into a single
        EditText, or digit-by-digit into 6 individual boxes (send_keys handles
        both cases since it just focuses the first field and types all 6 chars).
        """
        if method == "email" and email:
            _ipc.log("info", "📬 Fetching OTP from Gmail…")
            gmail = GmailWorkflow(self.device, self.device_id)

            if gmail_password:
                # Password provided — ensure the account is present on the device
                # (adds it via the Gmail app if it was never set up here).
                add_result = gmail.ensure_account_added(email, gmail_password)
                if not add_result["success"]:
                    _ipc.log("warning", f"⚠️ Could not add Gmail account: {add_result['message']}")
                    # Non-fatal — account may already be present from a previous run
            else:
                # No password — assume the account was already added via the Gmail
                # tab (pre-configured).  Skip ensure_account_added and go straight
                # to reading the inbox.
                _ipc.log("info", "⏩ Gmail password not provided — assuming account already on device")

            # Fetch the code — TikTok emails come from "TikTok" or "info@tiktok.com"
            otp_result = gmail.get_latest_verification_code(
                email=email,
                sender_filter="TikTok",
                timeout=120,
            )

            if not otp_result["success"] or not otp_result.get("code"):
                err_type = otp_result.get("error_type", "otp_not_received")
                # If account_not_in_switcher → let the front-end suggest going
                # to the Gmail tab to add the account first.
                return self._error(
                    err_type,
                    otp_result.get("message", "TikTok OTP not received within timeout"),
                )

            code = otp_result["code"]
            _ipc.log("info", f"✅ OTP retrieved: {code}")

            # Switch back to TikTok
            _ipc.log("info", "🔄 Returning to TikTok…")
            tiktok_pkg = self._get_tiktok_package()
            self.device.app_start(tiktok_pkg)
            time.sleep(1.5)

        else:
            # method="phone" or no email — SMS OTP not yet automated
            return self._error(
                "otp_not_automated",
                f"OTP automation not available for method={method}. "
                "Use the Email method with a Gmail account.",
            )

        # Enter the code in the TikTok OTP field
        otp_el = self._find_element(SIGNUP_SELECTORS.otp_input, timeout=8.0)
        if not otp_el:
            return self._error("otp_input_not_found",
                               "OTP input field not found on TikTok screen")

        otp_el.click()
        time.sleep(0.3)
        # Use send_keys — it handles both single 6-digit field and
        # a grid of 6 individual digit boxes (types into focused field)
        self.device.send_keys(code)
        time.sleep(0.5)

        # TikTok usually auto-submits when all 6 digits are entered.
        # Click Continue as fallback.
        self._click_selector(SIGNUP_SELECTORS.otp_continue_button, timeout=3.0)

        _ipc.log("info", "✅ OTP entered")
        return {"success": True}

    def _handle_password(self, tiktok_password: Optional[str]) -> dict:
        """
        Fill in the TikTok password creation screen and click Continuer.

        TikTok rules: 8–20 chars, ≥1 letter, ≥1 digit, ≥1 special char (#?!@).
        If tiktok_password is None a valid password is generated automatically.
        """
        import random
        import string as _string

        if not tiktok_password:
            # Generate a valid password: letter + digit + special + 5 random alphanums
            base = (
                random.choice(_string.ascii_letters)
                + random.choice(_string.digits)
                + random.choice("#?!@")
                + "".join(random.choices(_string.ascii_letters + _string.digits, k=5))
            )
            tiktok_password = "".join(random.sample(base, len(base)))
            _ipc.log("info", f"🔐 Generated password for new account")

        pwd_el = self._find_element(SIGNUP_SELECTORS.password_input, timeout=5.0)
        if not pwd_el:
            return self._error("password_input_not_found",
                               "Password input field not found")

        pwd_el.click()
        time.sleep(0.3)
        self.device.send_keys(tiktok_password, clear=True)
        time.sleep(0.5)

        if not self._click_selector(SIGNUP_SELECTORS.password_continue_button, timeout=5.0):
            return self._error("password_continue_not_found",
                               "Could not click Continue on password screen")

        _ipc.log("info", "✅ Password set")
        return {"success": True}

    def _handle_nickname(self, nickname: Optional[str]) -> dict:
        """
        Handle the TikTok nickname (username) screen.

        If nickname is None → click Ignorer (Skip).
        Otherwise type the nickname and click Continuer.
        """
        if not nickname:
            if not self._click_selector(SIGNUP_SELECTORS.nickname_skip_button, timeout=5.0):
                # Skip button not found — try Continue anyway (default username assigned)
                self._click_selector(SIGNUP_SELECTORS.nickname_continue_button, timeout=3.0)
            _ipc.log("info", "⏩ Nickname skipped")
            return {"success": True}

        nick_el = self._find_element(SIGNUP_SELECTORS.nickname_input, timeout=5.0)
        if not nick_el:
            return self._error("nickname_input_not_found",
                               "Nickname input field not found")

        nick_el.click()
        time.sleep(0.3)
        self.device.send_keys(nickname, clear=True)
        time.sleep(0.5)

        if not self._click_selector(SIGNUP_SELECTORS.nickname_continue_button, timeout=5.0):
            return self._error("nickname_continue_not_found",
                               "Could not click Continue on nickname screen")

        _ipc.log("info", f"✅ Nickname set: {nickname}")
        return {"success": True}

    def _get_tiktok_package(self) -> str:
        """
        Return the TikTok package name actually installed on the device.
        Falls back to the musically package if detection fails.
        """
        for pkg in ("com.ss.android.ugc.trill", TIKTOK_PACKAGE):
            try:
                result = self.device.shell(f"pm list packages {pkg}")
                if pkg in result:
                    return pkg
            except Exception:
                pass
        return TIKTOK_PACKAGE

    def _select_country_code(self, country_name: str) -> bool:
        """
        Open the country picker, search for country_name, and tap the first result.
        Non-blocking: if anything fails mid-way the picker is closed and False is returned.
        The phone tab screen is preserved in either case.
        """
        # Open picker via the country code button (e.g. "US +1")
        if not self._click_selector(SIGNUP_SELECTORS.country_code_selector, timeout=5.0):
            _ipc.log("warning", "⚠️ Could not open country picker — keeping default country")
            return False

        time.sleep(1.0)

        # Verify the picker screen appeared
        if not self._find_element(COUNTRY_PICKER_SELECTORS.screen_indicator, timeout=6.0):
            _ipc.log("warning", "⚠️ Country picker screen not detected — keeping default country")
            return False

        # Type in the search field
        search_el = self._find_element(COUNTRY_PICKER_SELECTORS.search_input, timeout=5.0)
        if not search_el:
            _ipc.log("warning", "⚠️ Country search field not found — closing picker")
            self._click_selector(COUNTRY_PICKER_SELECTORS.close_button, timeout=3.0)
            return False

        search_el.click()
        time.sleep(0.3)
        self.device.send_keys(country_name, clear=True)
        time.sleep(1.2)  # wait for filtered results

        # Tap the first result
        if not self._click_selector(COUNTRY_PICKER_SELECTORS.first_country_item, timeout=5.0):
            _ipc.log("warning", f"⚠️ No country found for '{country_name}' — closing picker")
            self._click_selector(COUNTRY_PICKER_SELECTORS.close_button, timeout=3.0)
            return False

        _ipc.log("info", f"✅ Country selected: {country_name}")
        time.sleep(0.5)
        return True
