"""Shared popup handling logic for all TikTok workflows.

Centralises the popup-detection-and-close chain that was duplicated
across ForYouWorkflow, SearchWorkflow, and FollowersWorkflow.
"""

import time
from loguru import logger

from taktik.core.shared.device.ui_dump import parse_bounds, parse_ui_dump

SYSTEM_UI_PACKAGE = 'com.android.systemui'
# The OCR behind an unlabelled dialog costs a screenshot and a Tesseract pass: at most one try in
# this window, however often the chain runs.
UNLABELLED_OVERLAY_RETRY_SECONDS = 30.0


def unlabelled_overlay_region(tree):
    """The frame of an app dialog that exposes no readable node, or None.

    The "update the app" prompt of TikTok 43.1.4 is drawn without a single text or content-desc:
    no selector can see it, Back does not close it, and every tap of the run lands on the dim
    layer behind it. Its signature is structural: the app's nodes are there, none carries a
    label, and one of them is smaller than the screen (the dialog's frame). A loading screen
    that fills the screen does not qualify.
    """
    app_nodes = [node for node in tree.iter()
                 if node.get('package') and node.get('package') != SYSTEM_UI_PACKAGE]
    if not app_nodes:
        return None
    if any((node.get('text') or '').strip() or (node.get('content-desc') or '').strip()
           for node in app_nodes):
        return None
    boxes = [parse_bounds(node.get('bounds') or '') for node in app_nodes]
    boxes = [box for box in boxes if box and box[2] > box[0] and box[3] > box[1]]
    if not boxes:
        return None
    screen = max(boxes, key=lambda box: (box[2] - box[0]) * (box[3] - box[1]))
    inner = [box for box in boxes if box != screen]
    if not inner:
        return None
    return min(inner, key=lambda box: (box[2] - box[0]) * (box[3] - box[1]))


class PopupHandler:
    """Stateless helper that closes TikTok popups using click + detection actions.

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

        # Ce dump etait lu puis jete. C'est le passage le plus frequent d'un run TikTok, donc
        # celui qui rend l'anneau des ecrans vivant -- et il ne coute rien de plus a l'appareil.
        try:
            from taktik.core.shared.diagnostics.screen_ring import noter as _noter_ecran
            _noter_ecran(xml, platform='tiktok')
        except Exception:  # noqa: BLE001
            pass

        def hit(selectors):
            for xp in (selectors if isinstance(selectors, list) else [selectors]):
                try:
                    if tree.xpath(xp):
                        return True
                except Exception:
                    continue
            return False

        from .....ui.selectors.shell.navigation import NAVIGATION_SELECTORS
        from .....ui.selectors.shell.popups import POPUP_SELECTORS
        from .....ui.selectors.surfaces.inbox import INBOX_SELECTORS

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
        if hit(POPUP_SELECTORS.gdpr_popup):
            found.add('gdpr')
        if hit(POPUP_SELECTORS.follow_friends_popup):
            found.add('follow_friends')
        if hit(POPUP_SELECTORS.collections_popup):
            found.add('collections')
        if hit(POPUP_SELECTORS.close_button) or hit(POPUP_SELECTORS.dismiss_button):
            found.add('generic_popup')
        if hit(POPUP_SELECTORS.video_options_sheet):
            found.add('video_options_sheet')
        if not found:
            self._overlay_region = unlabelled_overlay_region(tree)
            if self._overlay_region is not None:
                found.add('unlabelled_overlay')
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

        Falls back transparently to sequential polling when the hierarchy
        dump fails or does not parse.
        """
        detected = self._fast_detect()

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
