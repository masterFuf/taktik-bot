"""Shared popup handling logic for all TikTok workflows.

Centralises the popup-detection-and-close chain that was duplicated
across ForYouWorkflow, SearchWorkflow, and FollowersWorkflow.
"""

import time
from loguru import logger

from taktik.core.shared.device.ui_dump import parse_ui_dump

# The popup families and the unlabelled dialog belong to the detection layer, which also reads
# them on a screen photo (`read_screen`); `unlabelled_overlay_region` stays importable from here.
from ....atomic.detection.screen_reading import popup_families, unlabelled_overlay_region

# The OCR behind an unlabelled dialog costs a screenshot and a Tesseract pass: at most one try in
# this window, however often the chain runs.
UNLABELLED_OVERLAY_RETRY_SECONDS = 30.0


def _note_screen(xml) -> None:
    """The most frequent read of a TikTok run is what keeps the screen ring alive, at no cost to
    the phone."""
    try:
        from taktik.core.shared.diagnostics.screen_ring import noter as _noter_ecran
        _noter_ecran(xml, platform='tiktok')
    except Exception:  # noqa: BLE001
        pass


class PopupHandler:
    """Helper that closes TikTok popups using click + detection actions.

    Usage::

        handler = PopupHandler(click_actions, detection_actions)
        closed = handler.close_all()   # returns True if something was closed

    Some of what this closes is not a popup but a SURFACE the app dropped us on by
    accident — the inbox in particular, which new accounts on some devices get pushed
    to repeatedly. Escaping it is right for a workflow browsing videos and wrong for
    one whose target IS the inbox, so the workflow declares what it owns once, at
    construction, through ``owned_surfaces``. An owned surface is never escaped.
    """

    def __init__(self, click, detection, owned_surfaces=frozenset()):
        self.click = click
        self.detection = detection
        self.owned_surfaces = frozenset(owned_surfaces)
        self.logger = logger.bind(module="tiktok-popup-handler")
        self._overlay_region = None
        self._last_overlay_try = 0.0

    # ------------------------------------------------------------------
    # Fast single-dump scanner
    # ------------------------------------------------------------------

    def _fast_detect(self):
        """Dump hierarchy once and check all popup indicators on the `parse_ui_dump` tree.

        Returns a set of strings indicating what's present on screen.
        Returns ``{'_fallback'}`` when the fast path is unavailable so that
        ``close_all()`` can fall back to the original slow polling path.
        Returns an empty set when nothing popup-related is found (fast exit).
        """
        try:
            xml = self.detection.device.dump_hierarchy(compressed=False)
            tree = parse_ui_dump(xml)
            if tree is None:
                raise ValueError("unparseable hierarchy dump")
        except Exception as exc:
            self.logger.debug(f"_fast_detect: dump failed ({exc}) — falling back")
            return {'_fallback'}

        _note_screen(xml)

        def hit(selectors):
            for xp in (selectors if isinstance(selectors, list) else [selectors]):
                try:
                    if tree.xpath(xp):
                        return True
                except Exception:
                    continue
            return False

        found = popup_families(hit)
        if not found:
            self._overlay_region = unlabelled_overlay_region(tree)
            if self._overlay_region is not None:
                found.add('unlabelled_overlay')
        return found

    def detect(self, screen=None):
        """What needs handling: the popup families found, `'unlabelled_overlay'`, or
        `{'_fallback'}` when the screen could not be read. On `screen` (a `read_screen()`), read
        from its photo; without, from one dump of its own (`_fast_detect`)."""
        if screen is None:
            return self._fast_detect()
        if screen.photo is None:
            return {'_fallback'}
        _note_screen(screen.photo.xml)
        self._overlay_region = screen.overlay_region
        return set(screen.popups)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def close_all(self, screen=None) -> bool:
        """Run through the full popup chain. Returns True if any popup was closed: a gesture, so
        the caller reads the screen again.

        Fast path: a single dump_hierarchy() + lxml XPath scan is used to
        determine in ~0.5 s whether *anything* needs handling.  When the
        screen is clean this avoids the ~15 s of sequential per-selector
        polling that the original implementation would burn. Handed `screen`
        (the photo this turn was read on), it takes no dump at all.

        Falls back transparently to sequential polling when the hierarchy
        dump fails or does not parse.
        """
        detected = self.detect(screen)

        # ── Fallback: dump failed or unparseable ──────────────────────
        if '_fallback' in detected:
            return self._close_all_slow()

        # ── Fast exit: screen is clean ────────────────────────────────
        if not detected:
            return False

        # ── Handle in priority order ──────────────────────────────────

        if 'unlabelled_overlay' in detected:
            now = time.time()
            if now - self._last_overlay_try < UNLABELLED_OVERLAY_RETRY_SECONDS:
                return False
            self._last_overlay_try = now
            if self.click.dismiss_update_prompt(self._overlay_region):
                self.logger.info("✅ Update prompt dismissed (read by OCR)")
                time.sleep(0.8)
                return True
            return False

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

        # Dropped on the inbox page, unless this workflow owns it
        if 'inbox_page' in detected and 'inbox_page' not in self.owned_surfaces:
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

        if 'gdpr' in detected:
            if self.click.close_gdpr_popup():
                self.logger.info("GDPR popup closed")
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

        # Video options bottom sheet (longpress menu: Download, Not interested, Report...)
        # Close via back button — tapping outside would interact with the video
        if 'video_options_sheet' in detected:
            self.detection.device.press('back')
            self.logger.info("✅ Video options bottom sheet dismissed (back button)")
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
        from .....ui.selectors.shell.popups import POPUP_SELECTORS

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

        # Dropped on the inbox page, unless this workflow owns it
        if 'inbox_page' not in self.owned_surfaces and self.detection.is_on_inbox_page():
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

        if self.detection.has_gdpr_popup():
            if self.click.close_gdpr_popup():
                self.logger.info("GDPR popup closed")
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

        # Video options bottom sheet (longpress menu)
        if self.detection._element_exists(POPUP_SELECTORS.video_options_sheet, timeout=1):
            self.detection.device.press('back')
            self.logger.info("✅ Video options bottom sheet dismissed (back button)")
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
