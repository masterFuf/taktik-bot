"""Shared popup handling logic for all TikTok workflows.

Centralises the popup-detection-and-close chain that was duplicated
across ForYouWorkflow, SearchWorkflow, and FollowersWorkflow.
"""

import re as _re
import time
from loguru import logger


# XPath rewriter: converts Android class-name steps to lxml node[@class=…] form.
# e.g. //android.widget.Button[@text="x"] → //node[@class="android.widget.Button"][@text="x"]
_CLASS_STEP_RE = _re.compile(
    r'(/{1,2})([a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*)+)'
)


def _to_lxml(xp: str) -> str:
    return _CLASS_STEP_RE.sub(r'\1node[@class="\2"]', xp)


class PopupHandler:
    """Stateless helper that closes TikTok popups using click + detection actions.

    Usage::

        handler = PopupHandler(click_actions, detection_actions)
        closed = handler.close_all()   # returns True if something was closed
    """

    def __init__(self, click, detection):
        self.click = click
        self.detection = detection
        self.logger = logger.bind(module="tiktok-popup-handler")

    # ------------------------------------------------------------------
    # Fast single-dump scanner
    # ------------------------------------------------------------------

    def _fast_detect(self):
        """Dump hierarchy once and check all popup indicators via lxml.

        Returns a set of strings indicating what's present on screen.
        Returns ``{'_fallback'}`` when the fast path is unavailable so that
        ``close_all()`` can fall back to the original slow polling path.
        Returns an empty set when nothing popup-related is found (fast exit).
        """
        try:
            from lxml import etree
        except ImportError:
            return {'_fallback'}

        try:
            xml = self.detection.device.dump_hierarchy(compressed=False)
            tree = etree.fromstring(xml.encode('utf-8'))
        except Exception as exc:
            self.logger.debug(f"_fast_detect: dump failed ({exc}) — falling back")
            return {'_fallback'}

        def hit(selectors):
            for xp in (selectors if isinstance(selectors, list) else [selectors]):
                try:
                    if tree.xpath(_to_lxml(xp)):
                        return True
                except Exception:
                    continue
            return False

        from .....ui.selectors import (
            POPUP_SELECTORS,
            INBOX_SELECTORS,
            NAVIGATION_SELECTORS,
        )

        found = set()
        if hit(POPUP_SELECTORS.system_deny_button):
            found.add('system_deny')
        if hit(POPUP_SELECTORS.system_input_method_popup):
            found.add('system_input')
        if hit(POPUP_SELECTORS.system_dialog):
            found.add('system_dialog')
        if hit(POPUP_SELECTORS.notification_banner):
            found.add('notification_banner')
        if hit(INBOX_SELECTORS.inbox_title) or hit(NAVIGATION_SELECTORS.inbox_tab_selected):
            found.add('inbox_page')
        if hit(POPUP_SELECTORS.link_email_popup):
            found.add('link_email')
        if hit(POPUP_SELECTORS.follow_friends_popup):
            found.add('follow_friends')
        if hit(POPUP_SELECTORS.collections_popup):
            found.add('collections')
        if hit(POPUP_SELECTORS.close_button) or hit(POPUP_SELECTORS.dismiss_button):
            found.add('generic_popup')
        return found

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def close_all(self) -> bool:
        """Run through the full popup chain. Returns True if any popup was closed.

        Fast path: a single dump_hierarchy() + lxml XPath scan is used to
        determine in ~0.5 s whether *anything* needs handling.  When the
        screen is clean this avoids the ~15 s of sequential per-selector
        polling that the original implementation would burn.

        Falls back transparently to sequential polling when lxml is
        unavailable or when the hierarchy dump fails.
        """
        detected = self._fast_detect()

        # ── Fallback: lxml unavailable or dump failed ─────────────────
        if '_fallback' in detected:
            return self._close_all_slow()

        # ── Fast exit: screen is clean ────────────────────────────────
        if not detected:
            return False

        # ── Handle in priority order ──────────────────────────────────

        # Android system popups: permission dialogs
        if 'system_deny' in detected or 'system_input' in detected or 'system_dialog' in detected:
            if self.click.close_system_popup():
                self.logger.info("✅ System popup closed")
                time.sleep(0.5)
                return True

        # Notification banner (e.g., "X sent you new messages")
        if 'notification_banner' in detected:
            if self.click.dismiss_notification_banner():
                self.logger.info("✅ Notification banner dismissed")
                time.sleep(0.5)
                return True

        # Accidentally on Inbox page
        if 'inbox_page' in detected:
            self.click.escape_inbox_page()
            self.logger.info("✅ Escaped from Inbox page")
            time.sleep(1.0)  # Samsung needs extra time to complete the transition
            return True

        # "Link email" popup
        if 'link_email' in detected:
            if self.click.close_link_email_popup():
                self.logger.info("✅ 'Link email' popup closed")
                time.sleep(0.5)
                return True

        # "Follow your friends" popup
        if 'follow_friends' in detected:
            if self.click.close_follow_friends_popup():
                self.logger.info("✅ 'Follow your friends' popup closed")
                time.sleep(0.5)
                return True

        # Collections popup
        if 'collections' in detected:
            if self.click.close_collections_popup():
                self.logger.info("✅ Collections popup closed")
                time.sleep(0.5)
                return True

        # Generic popup (close / dismiss button)
        if 'generic_popup' in detected:
            self.logger.info("🚨 Popup detected, attempting to close")
            if self.click.close_popup():
                self.logger.info("✅ Popup closed")
                time.sleep(0.5)
                return True

        return False

    # ------------------------------------------------------------------
    # Slow fallback (original sequential polling)
    # ------------------------------------------------------------------

    def _close_all_slow(self) -> bool:
        """Original sequential-polling implementation used as fallback."""

        # Android system popups (input method selection, etc.)
        if self.click.close_system_popup():
            self.logger.info("✅ System popup closed")
            time.sleep(0.5)
            return True

        # Notification banner (e.g., "X sent you new messages")
        if self.click.dismiss_notification_banner():
            self.logger.info("✅ Notification banner dismissed")
            time.sleep(0.5)
            return True

        # Accidentally on Inbox page
        if self.detection.is_on_inbox_page():
            self.click.escape_inbox_page()
            self.logger.info("✅ Escaped from Inbox page")
            time.sleep(0.5)
            return True

        # "Link email" popup
        if self.detection.has_link_email_popup():
            if self.click.close_link_email_popup():
                self.logger.info("✅ 'Link email' popup closed")
                time.sleep(0.5)
                return True

        # "Follow your friends" popup
        if self.detection.has_follow_friends_popup():
            if self.click.close_follow_friends_popup():
                self.logger.info("✅ 'Follow your friends' popup closed")
                time.sleep(0.5)
                return True

        # Collections popup
        if self.detection.has_collections_popup():
            if self.click.close_collections_popup():
                self.logger.info("✅ Collections popup closed")
                time.sleep(0.5)
                return True

        # Generic popup
        if self.detection.has_popup():
            self.logger.info("🚨 Popup detected, attempting to close")
            if self.click.close_popup():
                self.logger.info("✅ Popup closed")
                time.sleep(0.5)
                return True

        return False
