"""Reading the verification code Google mails during a sign-in.

Split out of `account.py`, which carried four unrelated jobs in one class. This one is
self-contained: it searches the inbox and parses a code out of what it finds, and touches
none of the account-management state around it.

A mixin rather than free functions, so the call sites keep working unchanged: the methods
still reach `self.device`, `self.logger` and the element helpers the workflow provides.
"""

import re
import time
from typing import Optional

from taktik.core.app.email.gmail.ui.selectors import GMAIL_INBOX_SELECTORS
from taktik.core.app.email.gmail.workflows._notifier import _ipc, _with_bound_notifier

# How long to keep refreshing the inbox waiting for the mail to land, and how often.
_OTP_POLL_TIMEOUT = 120
_OTP_POLL_INTERVAL = 5


class GmailOtpReadingMixin:
    """Search the inbox for a verification code and read it."""

    @_with_bound_notifier
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
