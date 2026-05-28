"""
TikTok Upload Workflow
======================
Publie une vidéo ou une image sur TikTok depuis un fichier local.

Flow :
  1. Pousse le fichier via ADB vers /sdcard/DCIM/Camera/
  2. Déclenche le media scan pour qu'il apparaisse dans la galerie
  3. Ouvre TikTok → tap bouton "+"
  4. Tap "Upload" pour ouvrir la galerie (au lieu de l'enregistrement caméra)
  5. Sélectionne le premier fichier (le plus récent = celui qu'on vient de pousser)
  6. Tape "Next" / "Suivant" autant que nécessaire
  7. Saisit la description (caption + hashtags)
  8. Tape "Post" / "Publier"
"""

from __future__ import annotations

import os
import subprocess
import time

from loguru import logger

# Splash activity used by all TikTok package variants.
# Using this with app_start() makes the launch non-blocking (am start -n pkg/activity)
# and is the same mechanism used by TikTokManager.restart() in the automation workflows.
_TIKTOK_SPLASH_ACTIVITY = "com.ss.android.ugc.aweme.splash.SplashActivity"

from taktik.core.shared.device.media_store import (
    push_media,
    trigger_media_scan,
    scan_wait_for,
)
from taktik.core.shared.device.permissions import PermissionHandler
from taktik.core.social_media.tiktok.services.package_resolver import resolve_tiktok_package
from taktik.core.social_media.tiktok.services.publish_caption import (
    MAX_TIKTOK_HASHTAGS,
    build_caption,
    sanitize_caption_and_hashtags,
)
from taktik.core.social_media.tiktok.services.publish_commit import (
    PublishCommitCallbacks,
    wait_for_publish_commit,
)
from taktik.core.social_media.tiktok.services.publish_progress import get_publish_progress_percent
from taktik.core.social_media.tiktok.ui.detectors.keyboard import dismiss_keyboard
from taktik.core.social_media.tiktok.ui.selectors import PUBLISH_SELECTORS, POPUP_SELECTORS
from taktik.core.social_media.tiktok.ui.xpath import find_element, parse_bounds, tap_element, to_lxml

try:
    from bridges.common.ipc import IPC as _IPC
    _ipc = _IPC()
except Exception:
    class _FallbackIPC:
        def log(self, level, msg): logger.info(msg)
        def status(self, s, m=""): logger.info(f"[{s}] {m}")
    _ipc = _FallbackIPC()

# ---------------------------------------------------------------------------
# Sélecteurs
# ---------------------------------------------------------------------------
# Tous les sélecteurs sont centralisés dans
#   taktik/core/social_media/tiktok/ui/selectors/publish.py
# Voir ce fichier pour l'historique des resource-ids par version d'app TikTok.
#
# Les sélecteurs des popups système Android (autorisations) sont gérés par
# `PermissionHandler` (taktik/core/shared/device/permissions.py), qui sait
# détecter la version d'Android et la langue système.

# ── XPath lxml translator (identique au signup_workflow) ─────────────────────
# ---------------------------------------------------------------------------
# Workflow class
# ---------------------------------------------------------------------------

class TikTokUploadWorkflow:
    """
    Publie un fichier média sur TikTok.

    Parameters
    ----------
    device      : uiautomator2 device object
    device_id   : ADB serial (e.g. "C57S00000032140")
    """

    _EXIST_TIMEOUT = 2.0  # secondes pour les recherches rapides

    def __init__(self, device, device_id: str):
        self.device = device
        self.device_id = device_id

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    def execute(
        self,
        local_path: str,
        caption: str = "",
        hashtags: list[str] | None = None,
        package_name: str | None = None,
    ) -> dict:
        """
        Publie le fichier local_path sur TikTok.

        Returns
        -------
        dict avec keys :  success (bool), message (str), error_type (str | None)
        """
        caption, hashtags, dropped_hashtags = sanitize_caption_and_hashtags(caption, hashtags)
        if dropped_hashtags:
            _ipc.log(
                "warning",
                f"TikTok accepts {MAX_TIKTOK_HASHTAGS} hashtags maximum; "
                f"{dropped_hashtags} extra hashtag(s) were removed."
            )

        # 1. Vérifier que le fichier existe
        if not os.path.isfile(local_path):
            return self._error("file_not_found", f"File not found: {local_path}")

        # 2-3. Push file + trigger MediaStore indexing (shared service)
        _ipc.log("info", f"📤 Pushing file to device: {os.path.basename(local_path)}")
        remote_path = push_media(self.device_id, local_path)
        if not remote_path:
            return self._error("push_failed", "Failed to push file to device")

        _ipc.log("info", "🔄 Triggering media scan...")
        trigger_media_scan(self.device_id, remote_path, local_path, log=_ipc.log)
        # Wait for MediaStore to index (videos take longer due to metadata extraction)
        time.sleep(scan_wait_for(local_path))

        # 4-5. Force-stop TikTok and relaunch — same pattern as automation workflows.
        # TikTokManager.restart() calls device.app_start(pkg, SplashActivity, stop=True),
        # which translates to `am start -S -n pkg/SplashActivity` (fast, non-blocking).
        # We replicate that here so publish and automation share the same boot path.
        tiktok_pkg = package_name or resolve_tiktok_package(self.device_id)
        _ipc.log("info", "🔄 Restarting TikTok (force stop + fresh launch)...")
        _ipc.status("navigating", "Restarting TikTok...")
        try:
            self.device.app_start(tiktok_pkg, _TIKTOK_SPLASH_ACTIVITY, stop=True)
        except Exception as e:
            logger.debug(f"[launch] app_start failed ({e}), falling back to ADB monkey")
            self._adb_force_stop(tiktok_pkg)
            time.sleep(0.5)
            self._adb_launch_app(tiktok_pkg)
        # Wait for TikTok to fully load — 4s matches the automation bridge delay.
        # For very slow devices, also poll for the Create button before proceeding.
        time.sleep(4)
        self._wait_for_tiktok_home(timeout=30.0)
        _ipc.status("navigating", "TikTok ready")

        # 5b. Detect app language and prune wrong-language selectors in-place.
        # Home/For-You screen exposes bottom-nav labels used by language detection.
        # Non-fatal: failure leaves all selectors in place.
        try:
            from taktik.core.social_media.tiktok.ui.language import detect_and_optimize
            lang = detect_and_optimize(self.device)
            _ipc.log("info", f"🌐 TikTok language detected: {lang.upper()}")
        except Exception as e:
            _ipc.log("warning", f"Language detection failed (non-fatal): {e}")

        self._dismiss_post_popups()

        # 6. Appuyer sur le bouton Create
        _ipc.status("navigating", "Tapping Create button...")
        if not self._tap_create_button():
            return self._error("create_btn_not_found", "Create button not found")
        time.sleep(1.0)
        if self._handle_permission_dialog():
            time.sleep(1.0)

        # 7. Taper le bouton Upload/Gallery dans le panneau de création caméra
        _ipc.status("navigating", "Tapping Upload/Gallery button...")
        if not self._tap_upload():
            self._dismiss_post_popups()
            if self._handle_permission_dialog():
                time.sleep(0.8)
            if not self._tap_upload():
                return self._error("upload_btn_not_found", "Upload button not found in creation panel")
        if not self._ensure_gallery_picker_open():
            return self._error("gallery_not_opened", "TikTok gallery did not open after tapping Upload")

        # 8. Sélectionner le premier fichier de la galerie
        _ipc.status("selecting", "Selecting media from gallery...")
        if not self._select_first_gallery_item():
            return self._error("gallery_item_not_found", "Could not select media from gallery")
        time.sleep(1.2)  # wait for TikTok to enable the Next button after item selection

        # 8. Taper "Next" jusqu'à l'écran de description (max 3 fois)
        _ipc.status("navigating", "Navigating to post screen...")
        for _ in range(3):
            if self._is_on_post_screen():
                break
            if not self._tap(selectors=PUBLISH_SELECTORS.next_btn, timeout=3.0):
                break
            time.sleep(1.5)

        if not self._is_on_post_screen():
            return self._error("post_screen_not_reached", "TikTok post description screen was not reached")

        # 9. Saisir la description
        full_caption = build_caption(caption, hashtags)
        if full_caption:
            _ipc.status("filling", "Entering caption...")
            if not self._fill_caption(caption, hashtags):
                return self._error("caption_fill_failed", "Could not enter TikTok caption")
            time.sleep(0.5)

        # 10. Taper "Post"
        _ipc.status("publishing", "Publishing...")
        self._recover_from_video_edit_screen()
        if not self._tap(selectors=PUBLISH_SELECTORS.post_btn, timeout=5.0):
            self._recover_from_video_edit_screen()
            if self._tap(selectors=PUBLISH_SELECTORS.post_btn, timeout=3.0):
                time.sleep(3.0)
                self._dismiss_post_popups()
                _ipc.status("success", "Post published successfully!")
                _ipc.log("info", "âœ… TikTok post published")
                self._adb_force_stop(tiktok_pkg)
                return {"success": True, "message": "Post published successfully", "error_type": None}
            return self._error("post_btn_not_found", "Post button not found")

        time.sleep(1.8)

        # TikTok can ask for an extra confirmation before the real publication.
        if self._handle_publish_confirmation_dialog():
            time.sleep(1.2)

        # 11. Dismiss any system dialogs that may appear after posting
        # (e.g. Android "Add to Home Screen" / widget install prompt from TikTok)
        if not self._wait_for_publish_commit():
            return self._error(
                "publish_not_committed",
                "TikTok did not appear to finish publishing before timeout",
            )

        self._dismiss_post_popups()

        # 12. Vérification succès (best-effort)
        _ipc.status("success", "Post published successfully!")
        _ipc.log("info", "✅ TikTok post published")

        # 13. Close TikTok after successful post
        self._adb_force_stop(tiktok_pkg)

        return {"success": True, "message": "Post published successfully", "error_type": None}

    # ------------------------------------------------------------------
    # ADB helpers
    # ------------------------------------------------------------------

    def _adb_launch_app(self, package_name: str) -> None:
        """Launch an app via ADB in a fire-and-forget manner (non-blocking).

        Unlike uiautomator2's app_start(), this returns immediately without
        waiting for the activity to be ready. Polling is done separately.
        """
        try:
            subprocess.run(
                ['adb', '-s', self.device_id, 'shell', 'monkey',
                 '-p', package_name, '-c', 'android.intent.category.LAUNCHER', '1'],
                capture_output=True, text=True, timeout=5
            )
        except Exception:
            # monkey timed-out or failed — try am start as fallback
            try:
                subprocess.run(
                    ['adb', '-s', self.device_id, 'shell', 'am', 'start',
                     '-a', 'android.intent.action.MAIN',
                     '-c', 'android.intent.category.LAUNCHER',
                     '-p', package_name],
                    capture_output=True, text=True, timeout=5
                )
            except Exception as e:
                logger.debug(f'[launch] non-fatal launch error: {e}')

    def _adb_force_stop(self, package_name: str) -> None:
        """Force-stop an app package (non-fatal on error)."""
        try:
            subprocess.run(
                ['adb', '-s', self.device_id, 'shell', 'am', 'force-stop', package_name],
                capture_output=True, text=True, timeout=10
            )
        except Exception as e:
            logger.debug(f'[force-stop] non-fatal error: {e}')

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _wait_for_tiktok_home(self, timeout: float = 60.0) -> bool:
        """
        Poll until TikTok's home screen is ready (Create button or Home tab visible).

        This replaces a fixed time.sleep() after app_start so that:
        - Fast devices are not penalised (returns as soon as the button appears)
        - Slow/cold-start devices (e.g. 32-bit ARM) are given enough time

        Strategy: try each indicator selector for 2s, rotate through them,
        total cap = timeout.  Reports progress every 10s.
        """
        start = time.time()
        last_log = start
        while True:
            elapsed = time.time() - start
            if elapsed >= timeout:
                _ipc.log("warning", f"⚠️  TikTok home not detected after {timeout:.0f}s, proceeding anyway")
                return False
            for xp in PUBLISH_SELECTORS.home_ready_indicators:
                try:
                    if self.device.xpath(xp).wait(timeout=2.0):
                        _ipc.log("info", f"✅ TikTok home ready in {elapsed + (time.time() - start - elapsed):.1f}s")
                        return True
                except Exception:
                    pass
                if time.time() - start >= timeout:
                    break
            # Progress log every 10s so the UI doesn't look frozen
            now = time.time()
            if now - last_log >= 10.0:
                _ipc.log("info", f"⏳ Waiting for TikTok home... ({int(now - start)}s)")
                last_log = now

    def _tap_create_button(self) -> bool:
        """Tap the Create button in the bottom navigation bar."""
        if self._tap(PUBLISH_SELECTORS.create_btn, timeout=3.0):
            return True
        # Fallback: tap bottom nav at 40% width (Create is 3rd/5 items = 40% = center of 3rd slot)
        try:
            info = self.device.info
            w = info.get("displayWidth", 720)
            h = info.get("displayHeight", 1520)
            # Bottom nav starts at ~88% height; Create button is at ~40% width
            tap_x = int(w * 0.40)
            tap_y = int(h * 0.94)
            _ipc.log("debug", f"[create] fallback coord tap: ({tap_x}, {tap_y})")
            self.device.click(tap_x, tap_y)
            return True
        except Exception:
            return False

    def _tap_upload(self) -> bool:
        """Tap the gallery thumbnail in the camera creation panel."""
        if self._tap(PUBLISH_SELECTORS.upload_btn, timeout=6.0):
            return True
        if self._tap_upload_from_dump():
            return True
        # Fallback A: try ce9 position in the camera strip (right of shutter).
        # On C57S (576x1280): ce9 bounds [409,945][529,1065] → center=(469,1005) = (81%, 78%)
        # On larger devices this coordinate may be different; we'll try both fallbacks.
        try:
            info = self.device.info
            w = info.get("displayWidth", 720)
            h = info.get("displayHeight", 1520)
            # Try right-side gallery thumbnail (ce9 layout — C57S and similar)
            tap_x_r = int(w * 0.815)
            tap_y_strip = int(h * 0.785)
            _ipc.log("debug", f"[upload] fallback A (right-strip): ({tap_x_r}, {tap_y_strip})")
            self.device.click(tap_x_r, tap_y_strip)
            return True
        except Exception as e:
            _ipc.log("debug", f"[upload] fallback A failed: {e}")
        # Fallback B: bottom-left corner (ymg layout — Pixel 4 and larger screens)
        # ymg bounds on 1080x2280: [0,2023][187,2177] → center=(93,2100) = (8.6%, 92.1%)
        try:
            info = self.device.info
            w = info.get("displayWidth", 720)
            h = info.get("displayHeight", 1520)
            tap_x = int(w * 0.086)
            tap_y = int(h * 0.921)
            _ipc.log("debug", f"[upload] fallback B (bottom-left): ({tap_x}, {tap_y})")
            self.device.click(tap_x, tap_y)
            return True
        except Exception as e:
            _ipc.log("error", f"[upload] fallback B failed: {e}")
            return False

    def _tap_upload_from_dump(self) -> bool:
        """Tap the visible TikTok gallery button by reading its bounds from XML.

        TikTok can A/B test the create screen even on identical device models.
        Selectors live in PublishSelectors; this method only reads bounds.
        """
        try:
            from lxml import etree

            xml = self.device.dump_hierarchy(compressed=False)
            tree = etree.fromstring(xml.encode("utf-8"))
            candidates = []

            for rid, xpath in PUBLISH_SELECTORS.upload_dump_selectors:
                nodes = tree.xpath(xpath)
                for node in nodes:
                    bounds = node.attrib.get("bounds", "")
                    if not bounds:
                        continue
                    parsed_bounds = parse_bounds(bounds)
                    if parsed_bounds is None:
                        continue
                    left, top, right, bottom = parsed_bounds
                    width = right - left
                    height = bottom - top
                    if width <= 12 or height <= 12:
                        continue
                    if node.attrib.get("visible-to-user") == "false" or node.attrib.get("enabled") == "false":
                        continue
                    clickable = node.attrib.get("clickable") == "true"
                    candidates.append((not clickable, rid, left, top, right, bottom))

            if not candidates:
                return False

            candidates.sort()
            _, rid, left, top, right, bottom = candidates[0]
            tap_x = (left + right) // 2
            tap_y = (top + bottom) // 2
            _ipc.log("debug", f"[upload] dump bounds tap {rid}: ({tap_x}, {tap_y})")
            self.device.click(tap_x, tap_y)
            return True
        except Exception as e:
            _ipc.log("debug", f"[upload] dump bounds tap failed: {e}")
            return False

    def _ensure_gallery_picker_open(self, attempts: int = 3) -> bool:
        """Ensure the TikTok gallery picker is actually open after tapping Upload.

        On some Android/TikTok combinations the first tap only triggers the
        runtime permission dialog. After the permissions are granted, TikTok
        stays on the camera screen and needs the gallery thumbnail tapped again.
        """
        for attempt in range(1, attempts + 1):
            time.sleep(1.2)
            self._handle_permission_dialog()
            time.sleep(1.0)

            if self._is_gallery_picker_open():
                return True

            if self._is_on_camera_creation_screen():
                _ipc.log(
                    "info",
                    f"[upload] still on TikTok camera after upload tap; retrying gallery tap ({attempt}/{attempts})"
                )
                self._tap_upload()
                continue

            # Transitional screen: wait a little more before retrying.
            _ipc.log("debug", f"[upload] gallery not detected yet ({attempt}/{attempts}); retrying")
            self._tap_upload()

        time.sleep(1.0)
        self._handle_permission_dialog()
        return self._is_gallery_picker_open()

    def _is_gallery_picker_open(self) -> bool:
        """Return True when the TikTok media picker/grid is visible."""
        for selector in PUBLISH_SELECTORS.gallery_first_item:
            try:
                if self.device.xpath(selector).wait(timeout=0.4):
                    return True
            except Exception:
                pass

        try:
            xml = self.device.dump_hierarchy(compressed=False)
            xml_lower = xml.lower()
            return PUBLISH_SELECTORS.has_gallery_picker_marker(xml_lower)
        except Exception:
            return False

    def _is_on_camera_creation_screen(self) -> bool:
        """Return True when TikTok is on the camera/create screen, not picker/details."""
        try:
            xml = self.device.dump_hierarchy(compressed=False)
            xml_lower = xml.lower()
            return PUBLISH_SELECTORS.has_camera_creation_marker(xml_lower)
        except Exception:
            return False

    def _handle_permission_dialog(self) -> bool:
        """Grant any Android permission dialogs (media access, etc.).

        Delegates to the central PermissionHandler, which is aware of the
        Android SDK level and system language.
        """
        try:
            handler = PermissionHandler(self.device, self.device_id)
            if handler.deny_contacts_if_present(wait=0.8):
                _ipc.log("info", "🚫 Denied TikTok contacts permission dialog")
                return True
            dismissed = handler.grant(rounds=2, per_round_wait=1.5)
            if dismissed:
                _ipc.log("info", f"🔓 Granted {dismissed} permission dialog(s)")
                return True
        except Exception as e:
            _ipc.log("warning", f"Permission handler failed: {e}")
        return False

    def _dismiss_post_popups(self):
        """Dismiss any system or app dialogs that appear after posting.

        Known dialogs (TikTok 44.9 on Nokia 4.2 / Android 11):
          - "Add to Home Screen" (widget install) → Button text='CANCEL'
        """
        if self._tap(POPUP_SELECTORS.gdpr_got_it_button, timeout=1.5):
            _ipc.log("info", "[popup] dismissed TikTok GDPR data-transfer notice")
            time.sleep(0.5)
            return

        el = self._find_element(PUBLISH_SELECTORS.popup_cancel_buttons, timeout=3.0)
        if el:
            try:
                _ipc.log("info", "🚫 Dismissing post-publishing dialog...")
                el.click()
                time.sleep(0.5)
            except Exception as e:
                _ipc.log("debug", f"[dismiss_popup] click failed: {e}")

    def _handle_publish_confirmation_dialog(self) -> bool:
        """Confirm TikTok's optional 'Publier la vidéo publiquement ?' dialog."""
        if not self._find_element(PUBLISH_SELECTORS.publish_confirm_dialog, timeout=1.5):
            return False

        _ipc.log("info", "[publishing] confirming TikTok visibility dialog...")
        if self._tap(PUBLISH_SELECTORS.publish_confirm_btn, timeout=2.0):
            return True
        return False

    def _wait_for_publish_commit(self, timeout: float = 120.0) -> bool:
        callbacks = PublishCommitCallbacks(
            handle_publish_confirmation=self._handle_publish_confirmation_dialog,
            dismiss_popups=self._dismiss_post_popups,
            get_progress_percent=lambda: get_publish_progress_percent(self.device, log=_ipc.log),
            is_on_post_screen=self._is_on_post_screen,
            has_success_indicator=lambda: self._find_element(
                PUBLISH_SELECTORS.success_indicator,
                timeout=1.0,
            ) is not None,
        )
        return wait_for_publish_commit(callbacks, timeout=timeout, log=_ipc.log)

    def _select_first_gallery_item(self) -> bool:
        """
        Select the first (most recent) item in TikTok's gallery picker.

        Uses XPath selectors derived from real UI dumps — device-resolution-independent.
        The gallery thumbnail ImageViews (mub / nm8) are clickable=false; uiautomator2
        taps their center coordinates which Android routes to the parent clickable
        FrameLayout, so the selection works regardless of screen size.

        Selector history (from real UI dumps):
          mub  → ImageView inside each grid cell (Pixel 4 + C57S confirmed, both packages)
               Structure: GridView(i8o) → FrameLayout(clickable) → ImageView(mub, same bounds)
               Tapping mub propagates to parent FrameLayout (clickable=true)
          nm8  → TikTok v44.9+ Samsung builds (grid = ir_)
          i8o  → the GridView container itself (same on Pixel 4 and C57S)
        """
        if self._tap(PUBLISH_SELECTORS.gallery_first_item, timeout=5.0):
            return True
        # Fallback: no XPath selector matched — tap the first thumbnail by coordinates.
        # Gallery grid is typically in the top 35% of the screen (above the pull-to-refresh zone).
        # Most-recent item = top-left cell of a 3-column grid.
        # w/6 = center of first column; h*0.20 = first row just below any gallery header.
        try:
            info = self.device.info
            w = info.get("displayWidth", 720)
            h = info.get("displayHeight", 1520)
            tap_x = w // 6          # center of first column (3-col grid)
            tap_y = int(h * 0.20)   # first row, below ~header (~100px on most screens)
            _ipc.log("warning", f"[gallery] XPath selectors failed — coord fallback ({tap_x},{tap_y}). "
                     "Provide a dump from this device to add the correct resource-id.")
            self.device.click(tap_x, tap_y)
            time.sleep(1.0)
            if self._is_on_camera_creation_screen():
                _ipc.log("warning", "[gallery] coord fallback did not leave the camera screen")
                return False
            return True
        except Exception as e:
            _ipc.log("error", f"[gallery] coord fallback failed: {e}")
        return False

    def _is_on_post_screen(self) -> bool:
        """Check if we're on the post description screen."""
        try:
            xml = self.device.dump_hierarchy(compressed=False)
            if PUBLISH_SELECTORS.has_post_screen_marker(xml):
                return True

            from lxml import etree
            tree = etree.fromstring(xml.encode("utf-8"))
            for xp in PUBLISH_SELECTORS.post_screen_indicators:
                try:
                    if tree.xpath(to_lxml(xp)):
                        return True
                except Exception:
                    pass
            return False
        except Exception:
            return False

    def _is_video_edit_screen(self) -> bool:
        """Return True when TikTok opened the post-upload video editor."""
        try:
            xml = self.device.dump_hierarchy(compressed=False)
            return PUBLISH_SELECTORS.has_video_edit_screen_marker(xml)
        except Exception:
            return False

    def _recover_from_video_edit_screen(self) -> bool:
        """Leave TikTok's video editor if a misplaced tap opened it."""
        if not self._is_video_edit_screen():
            return False

        _ipc.log("warning", "[publish] video editor opened; tapping cancel selector to return to post screen")
        if self._tap(PUBLISH_SELECTORS.video_edit_cancel_btn, timeout=2.0):
            time.sleep(1.2)
            return True
        return False

    def _fill_caption(self, caption: str, hashtags: list[str]) -> bool:
        """Fill caption and validate TikTok hashtag suggestions one by one."""
        # ── Focus the EditText ───────────────────────────────────────────────
        el = self._find_element(PUBLISH_SELECTORS.caption_input, timeout=5.0)
        try:
            if el:
                el.click()
            else:
                info = self.device.info
                w = info.get("displayWidth", 576)
                h = info.get("displayHeight", 1280)
                self.device.click(w // 2, int(h * 0.30))
            time.sleep(0.5)
        except Exception as e:
            _ipc.log("warning", f"[caption] focus failed: {e}")

        if not self._clear_caption_text():
            _ipc.log("debug", "[caption] clear text skipped or failed")

        caption = (caption or "").strip()
        if caption and not self._type_caption_text(caption, delay_mean=85, delay_deviation=25):
            return False

        for index, tag in enumerate(hashtags or []):
            clean_tag = str(tag).lstrip("#").strip()
            if not clean_tag:
                continue

            prefix = " " if (index > 0 or caption) else ""
            token = f"{prefix}#{clean_tag}"
            if not self._type_caption_text(token, delay_mean=70, delay_deviation=18):
                return False

            time.sleep(0.25)
            if not self._confirm_hashtag_suggestion(clean_tag):
                _ipc.log("warning", f"[hashtag] could not confirm suggestion for #{clean_tag}")
                self._type_caption_text(" ", delay_mean=40, delay_deviation=10)
                time.sleep(0.15)

        self._dismiss_caption_keyboard()
        return True

    def _clear_caption_text(self) -> bool:
        try:
            from taktik.core.shared.input.taktik_keyboard import (
                activate_taktik_keyboard,
                clear_text_with_taktik_keyboard,
            )
            activate_taktik_keyboard(self.device_id)
            return clear_text_with_taktik_keyboard(self.device_id)
        except Exception as e:
            _ipc.log("debug", f"[caption] Taktik Keyboard clear failed: {e}")
            return False

    def _type_caption_text(self, text: str, delay_mean: int = 80, delay_deviation: int = 30) -> bool:
        """Type caption through Taktik Keyboard first, with slower human pacing."""
        if not text:
            return True

        try:
            from taktik.core.shared.input.taktik_keyboard import (
                type_with_taktik_keyboard,
            )
            if type_with_taktik_keyboard(
                self.device_id,
                text,
                delay_mean=delay_mean,
                delay_deviation=delay_deviation,
            ):
                _ipc.log("debug", "[caption] text inserted with Taktik Keyboard")
                return True
        except Exception as e:
            _ipc.log("debug", f"[caption] Taktik Keyboard failed: {e}")

        if all(ord(ch) < 128 for ch in text):
            try:
                escaped = text.replace("\\", "\\\\").replace(" ", "%s")
                escaped = escaped.replace("&", "\\&").replace("|", "\\|").replace(";", "\\;")
                result = subprocess.run(
                    ["adb", "-s", self.device_id, "shell", "input", "text", escaped],
                    capture_output=True,
                    text=True,
                    timeout=8,
                )
                if result.returncode == 0:
                    _ipc.log("debug", "[caption] text inserted with adb input text")
                    return True
                _ipc.log("debug", f"[caption] adb input text failed: {result.stderr}")
            except Exception as e:
                _ipc.log("debug", f"[caption] adb input text exception: {e}")

        return False

    def _dismiss_caption_keyboard(self) -> None:
        """Hide the keyboard without tapping the preview/editor area."""
        dismiss_keyboard(self.device, self.device_id, log=_ipc.log)
        return None

    def _tap_hashtag_suggestion_from_dump(self, expected_tag: str | None = None) -> bool:
        """Tap the first visible TikTok hashtag suggestion from the XML dump."""
        try:
            from lxml import etree

            xml = self.device.dump_hierarchy(compressed=False)
            tree = etree.fromstring(xml.encode("utf-8"))
            expected = f"#{str(expected_tag or '').lstrip('#').strip()}".lower()
            candidates = []

            nodes = []
            for xpath in PUBLISH_SELECTORS.hashtag_suggestion_nodes:
                nodes.extend(tree.xpath(xpath))

            for node in nodes:
                text = node.attrib.get("text", "")
                bounds = node.attrib.get("bounds", "")
                parsed_bounds = parse_bounds(bounds)
                if parsed_bounds is None:
                    continue
                left, top, right, bottom = parsed_bounds
                if top < 480:
                    continue
                exact = expected and text.lower() == expected
                candidates.append((not exact, top, left, text, right, bottom))

            if not candidates:
                return False

            candidates.sort()
            _, top, left, text, right, bottom = candidates[0]
            tap_x = (left + right) // 2
            tap_y = (top + bottom) // 2
            _ipc.log("debug", f"[hashtag] tapping suggestion {text!r} at ({tap_x}, {tap_y})")
            self.device.click(tap_x, tap_y)
            time.sleep(0.15)
            return True
        except Exception as e:
            _ipc.log("debug", f"[hashtag] dump suggestion tap failed: {e}")
            return False

    def _confirm_hashtag_suggestion(self, expected_tag: str | None = None) -> bool:
        """Tap the first item in TikTok's hashtag autocomplete suggestion list.

        After typing a `#word`, TikTok shows a suggestion dropdown above the keyboard.
        Without tapping a suggestion the dropdown stays open and blocks the Post button.

        Returns True if a suggestion was tapped, False if none was found.
        """
        if self._tap_hashtag_suggestion_from_dump(expected_tag):
            return True

        tapped = self._tap(PUBLISH_SELECTORS.hashtag_suggestion_rows, timeout=2.0)
        if tapped:
            _ipc.log("debug", "[hashtag] suggestion tapped ✅")
            time.sleep(0.3)
        return tapped

    # ------------------------------------------------------------------
    # uiautomator2 helpers
    # ------------------------------------------------------------------

    def _find_element(self, selectors: list, timeout: float = _EXIST_TIMEOUT):
        return find_element(self.device, selectors, timeout)

    def _tap(self, selectors: list, timeout: float = _EXIST_TIMEOUT) -> bool:
        return tap_element(self.device, selectors, timeout)

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _error(error_type: str, message: str) -> dict:
        _ipc.log("error", f"❌ {message}")
        return {"success": False, "message": message, "error_type": error_type}
