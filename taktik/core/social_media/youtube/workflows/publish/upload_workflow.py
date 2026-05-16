"""
YouTube Upload Workflow
=======================
Publie une vidéo (Short ou Video standard) sur YouTube depuis un fichier local.

Flow observé sur dumps :
  1. Push media → /sdcard/DCIM/Camera/ + trigger media scan
  2. YouTube home → tap bouton "Create" (pivot_bar, content-desc="Create")
  3. Permission dialog "Allow YouTube to take pictures..." → tap "WHILE USING THE APP"
  4. Écran upload :  tabs Video / Short / Live / Post → tap "Add from gallery"
  5. Galerie système ou YouTube gallery → sélectionner le premier item (le plus récent)
  6. Écran d'édition → saisir title / description
  7. Tap "Next" → tap "Upload video" / "Upload Short"

Tous les sélecteurs XPath sont centralisés dans :
    taktik.core.social_media.youtube.ui.selectors.upload  (UPLOAD_SELECTORS)
"""

from __future__ import annotations

import os
import time
from typing import Optional

from loguru import logger

from taktik.core.shared.device.media_store import push_and_scan
from taktik.core.shared.device.permissions import PermissionHandler, ALLOW_SELECTORS, DENY_SELECTORS
from taktik.core.shared.input.taktik_keyboard import (
    type_with_taktik_keyboard,
    clear_text_with_taktik_keyboard,
)
from taktik.core.social_media.youtube.ui.selectors import UPLOAD_SELECTORS, YOUTUBE_PACKAGE

try:
    from bridges.common.ipc import IPC as _IPC
    _ipc = _IPC()
except Exception:
    class _FallbackIPC:  # type: ignore
        def log(self, level, msg): logger.info(msg)
        def status(self, s, m=""): logger.info(f"[{s}] {m}")
    _ipc = _FallbackIPC()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(level: str, msg: str) -> None:
    _ipc.log(level, msg)
    getattr(logger, level, logger.info)(msg)


def _status(state: str, msg: str) -> None:
    _ipc.status(state, msg)


def _try_tap(device, selectors: list[str], timeout: float = 3.0, label: str = "") -> bool:
    """
    Find the first visible selector within `timeout` seconds, then tap it.

    Uses a single scan loop (like _wait_for_any) so total wait ≤ timeout,
    instead of waiting `timeout` per selector.  Logs which selector won.
    """
    found_sel = _wait_for_any(device, selectors, timeout=timeout, label=label)
    if not found_sel:
        return False
    try:
        device.xpath(found_sel).click()
        return True
    except Exception as e:
        _log("warning", f"⚠️  [{label or 'tap'}] element found but click failed: {e}")
        return False


def _wait_for_any(device, selectors: list[str], timeout: float = 10.0, label: str = "") -> Optional[str]:
    """
    Return the first selector that becomes visible within `timeout` seconds.

    Scans all selectors in a tight loop (0.5 s sleep between rounds).
    Logs the winning selector so you can see in real time which one matched.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        for sel in selectors:
            try:
                if device.xpath(sel).exists:
                    _log("debug", f"✅ [{label or 'found'}] selector: {sel}")
                    return sel
            except Exception:
                continue
        time.sleep(0.5)
    if label:
        _log("debug", f"❌ [{label}] no match after {timeout:.0f}s ({len(selectors)} selectors tried)")
    return None


# Alias court pour lisibilité dans le workflow
_S = UPLOAD_SELECTORS


# ---------------------------------------------------------------------------
# Workflow class
# ---------------------------------------------------------------------------

class YouTubeUploadWorkflow:
    """
    End-to-end YouTube video upload.

    Parameters
    ----------
    device      : uiautomator2 Device
    device_id   : str  — ADB serial
    """

    def __init__(self, device, device_id: str):
        self.device = device
        self.device_id = device_id
        self._perms = PermissionHandler(device, device_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(
        self,
        local_path: str,
        title: str = "",
        description: str = "",
        upload_type: str = "short",   # "short" | "video"
        visibility: str = "public",   # "public" | "unlisted" | "private"
    ) -> dict:
        """
        Run the full upload flow.  Returns {"success": bool, "message": str}.
        """
        d = self.device

        try:
            # ── Step 1: push media to device ────────────────────────────────
            _status("running", "Pushing media to device…")
            _log("info", f"📤 Pushing {os.path.basename(local_path)} to device")
            remote_path = push_and_scan(
                device_id=self.device_id,
                local_path=local_path,
                file_prefix="YT",
                log=_log,
                wait=True,
            )
            if not remote_path:
                return {"success": False, "message": "Failed to push media to device"}
            _log("info", f"✅ Pushed to {remote_path}")

            # ── Step 2: force-stop + restart YouTube from scratch ────────────
            # Close whatever is currently on screen (YouTube or any other app)
            # then relaunch YouTube fresh — same pattern as Instagram/TikTok workflows.
            _status("running", "Restarting YouTube…")
            d.app_stop(YOUTUBE_PACKAGE)
            _log("info", "🔄 YouTube closed — restarting…")
            time.sleep(1)
            d.app_start(YOUTUBE_PACKAGE, "com.google.android.youtube.app.honeycomb.Shell$HomeActivity")
            # Wait 4 s for YouTube to fully render (mirrors AppService launch_wait)
            time.sleep(4)

            # Navigate to home tab in case YouTube opened on a video/watch page
            _try_tap(d, _S.home_tab, timeout=3, label="nav-home")
            time.sleep(1)

            # ── Dismiss notification permission popup if present ──────────────
            # 1) System permission dialog (com.android.permissioncontroller)
            # 2) In-app YouTube dialog ("Activer les notifications" / "Enable notifications")
            if self._perms.deny_if_present(wait=3.0) or _try_tap(d, _S.notification_cancel, timeout=2, label="notif-cancel"):
                _log("info", "🔕 Dismissed notification permission popup")
                time.sleep(0.8)

            # ── Step 3: tap Create "+" ───────────────────────────────────────
            _status("running", "Tapping Create button…")
            if not _try_tap(d, _S.create_button, timeout=5, label="create-btn"):
                return {"success": False, "message": "Could not find Create (+) button"}
            time.sleep(1.5)

            # ── Step 4: dismiss permission dialog(s) if present ─────────────
            # Grant any camera/mic/storage permission dialogs after tapping Create.
            # Shared service: Android 9 (packageinstaller) + Android 10+ + FR/EN.
            _status("running", "Checking permissions…")
            n = self._perms.grant(rounds=3, per_round_wait=4)
            if n:
                _log("info", f"✅ Granted {n} permission dialog(s) after Create")

            # ── Step 5: select tab (Short / Video) ──────────────────────────
            _status("running", f"Selecting upload type: {upload_type}…")
            if upload_type == "short":
                _try_tap(d, _S.tab_short, timeout=3, label="tab-short")
            else:
                _try_tap(d, _S.tab_video, timeout=3, label="tab-video")
            time.sleep(1.5)  # wait for Shorts camera / upload screen transition

            # Grant camera/storage permission dialog that YouTube may show
            # specifically after the Short tab opens the camera view.
            n = self._perms.grant(rounds=3, per_round_wait=4)
            if n:
                _log("info", f"✅ Granted {n} permission dialog(s) after tab selection")
                time.sleep(0.8)

            # ── Step 6: tap "Add from gallery" ──────────────────────────────
            _status("running", "Opening gallery…")
            if not _try_tap(d, _S.add_from_gallery, timeout=8, label="add-from-gallery"):
                # Dump the current UI hierarchy for debugging
                try:
                    xml = d.dump_hierarchy()
                    # Log first 3000 chars so we can identify the missing selector
                    _log("debug", f"[ui-dump] {xml[:3000]}")
                except Exception as dump_err:
                    _log("debug", f"[ui-dump] failed: {dump_err}")
                return {"success": False, "message": "Could not find 'Add from gallery' button"}
            time.sleep(2)

            # ── Step 7: dismiss storage/media/camera permission if it appears ─────────
            # Some devices (Android 9, Blackview A80Pro) show the camera permission
            # AFTER tapping "Add from gallery" rather than after Create.
            n = self._perms.grant(rounds=3, per_round_wait=3)
            if n:
                _log("info", f"✅ Granted {n} permission dialog(s) after Add from gallery")

            # ── Step 8: select first item in gallery ─────────────────────────
            _status("running", "Selecting video from gallery…")
            if not _try_tap(d, _S.gallery_first_item, timeout=8, label="gallery-first"):
                return {"success": False, "message": "Could not select first item in gallery"}
            time.sleep(2)

            # ── Step 9: tap Next (may be needed multiple times) ──────────────
            # Flow varies by device/YouTube version:
            #   Samsung:  gallery → multi-select Next → trimming → caption
            #   A80Pro:   gallery → trim screen (OK) → camera+video → checkmark → caption
            # Up to 6 rounds to cover all intermediate screens.
            _status("running", "Navigating to edit screen…")
            for i in range(6):
                if _wait_for_any(d, _S.title_input, timeout=3, label=f"title-input-check-{i+1}"):
                    break  # Already on caption/title screen
                _log("debug", f"📍 Step 9 round {i+1}/6 — tapping next")
                _try_tap(d, _S.next_button, timeout=4, label=f"next-btn-{i+1}")
                time.sleep(2.5)  # transitions can be slow

            # ── Step 10: enter title ──────────────────────────────────────────
            if title:
                _status("running", "Entering title…")
                _log("info", f"✏️  Title: {title[:60]}")
                found_title_sel = _wait_for_any(d, _S.title_input, timeout=5, label="title-input-tap")
                if found_title_sel:
                    # Click the field FIRST so Android opens the keyboard and establishes
                    # the IME input connection. type_with_taktik_keyboard() activates
                    # Taktik Keyboard internally if needed — same pattern as Instagram.
                    try:
                        d.xpath(found_title_sel).click()
                        time.sleep(1.0)  # wait for keyboard open + input connection
                    except Exception:
                        pass
                    if not type_with_taktik_keyboard(self.device_id, title):
                        _log("warning", "⚠️  Taktik Keyboard failed for title, falling back to set_text")
                        try:
                            d.xpath(found_title_sel).set_text(title)
                        except Exception:
                            try:
                                d.send_keys(title)
                            except Exception as e:
                                _log("warning", f"⚠️  All title entry methods failed: {e}")
                    time.sleep(0.5)
                else:
                    _log("warning", "⚠️  Could not find title input — skipping")

            # ── Step 11: enter description via sub-screen ──────────────────
            # Tapping the description row opens a full-screen EditText (no hint/resource-id).
            if description:
                _log("info", f"✏️  Description: {description[:80]}")
                _status("running", "Entering description…")
                if _try_tap(d, _S.detail_row_description, timeout=3, label="desc-row"):
                    time.sleep(1)  # wait for sub-screen animation
                    if _wait_for_any(d, _S.description_edittext, timeout=4, label="desc-edittext"):
                        # Click field first, then type — same pattern as Instagram
                        try:
                            d.xpath(_S.description_edittext[0]).click()
                            time.sleep(1.0)  # wait for keyboard open + input connection
                        except Exception as e:
                            _log("warning", f"⚠️  Description click failed: {e}")
                        if not type_with_taktik_keyboard(self.device_id, description):
                            _log("warning", "⚠️  Taktik Keyboard failed for description, falling back to send_keys")
                            try:
                                d.send_keys(description)
                            except Exception as e:
                                _log("warning", f"⚠️  Description typing failed: {e}")
                        # press("back") dismisses keyboard if visible, then returns to details
                        d.press("back")
                        time.sleep(1)
                    else:
                        _log("warning", "⚠️  Description sub-screen not detected — skipping")
                        d.press("back")
                        time.sleep(0.5)
                else:
                    _log("warning", "⚠️  Could not find description row — skipping")

            # ── Step 11b: set visibility ────────────────────────────────────
            # ADB Keyboard (Taktik) is headless — no visual keyboard to dismiss.
            # uiautomator2's hide_keyboard() fails with AdbBroadcastError on it.
            # The title EditText may still be focused; tapping the visibility row
            # below will naturally unfocus it. No explicit dismiss needed.
            # YouTube defaults to private, so we must always set visibility.
            # We iterate candidate rows and skip any that open the audience/kids
            # sub-screen (detected by the "En savoir plus" info button).
            vis = visibility.lower() if visibility else "public"
            _log("info", f"🔒 Setting visibility: {vis}")
            _status("running", f"Setting visibility to {vis}…")
            vis_set = False
            for vis_candidate in _S.detail_row_visibility:
                try:
                    if not d.xpath(vis_candidate).exists:
                        continue
                except Exception:
                    continue
                _log("debug", f"🔍 Trying visibility row: {vis_candidate[:80]}")
                try:
                    d.xpath(vis_candidate).click()
                except Exception:
                    continue
                time.sleep(1.5)  # wait for sub-screen animation
                # Detect if we accidentally opened the audience/kids screen
                on_wrong_screen = any(
                    d.xpath(s).exists for s in _S.audience_screen_indicator
                )
                if on_wrong_screen:
                    _log("warning", "⚠️  Opened audience/kids screen (wrong row) — pressing back, trying next")
                    d.press("back")
                    time.sleep(1.5)
                    continue
                # Confirm we're on the Set Visibility screen (back button "Retour" in header)
                if _wait_for_any(d, _S.visibility_screen_indicator, timeout=4, label="visibility-screen"):
                    time.sleep(1.0)  # allow option rows to fully render before querying
                    vis_sels = _S.visibility_row.get(vis, [])
                    if vis_sels and _try_tap(d, vis_sels, timeout=4, label=f"visibility-{vis}"):
                        _log("info", f"✅ Visibility set to {vis}")
                        vis_set = True
                        time.sleep(0.5)
                    else:
                        _log("warning", f"⚠️  Could not find {vis} option — leaving default")
                    # Tap the in-app back button (header "Retour") to return to Add Details
                    if not _try_tap(d, _S.visibility_back_button, timeout=3, label="visibility-back"):
                        d.press("back")  # fallback to system back
                    time.sleep(1)
                else:
                    _log("warning", "⚠️  Visibility sub-screen not detected — going back")
                    d.press("back")
                    time.sleep(0.5)
                break  # done (success or gave up on this screen)
            if not vis_set:
                _log("warning", "⚠️  Could not find/reach visibility row — using YouTube default")

            # Dismiss keyboard if open (without navigating back).
            # Taktik/ADB Keyboard is headless — suppress AdbBroadcastError.
            try:
                d.hide_keyboard()
                time.sleep(0.5)
            except Exception:
                pass

            # ── Step 12: tap Upload / Post ────────────────────────────────────
            _status("running", "Uploading…")
            _log("info", "🚀 Tapping Upload / Post button")
            if not _try_tap(d, _S.upload_button, timeout=8, label="upload-btn"):
                return {"success": False, "message": "Could not find Upload/Post button"}

            # ── Step 13: wait for confirmation ───────────────────────────────
            _status("running", "Waiting for upload confirmation…")
            done_sel = _wait_for_any(d, _S.upload_done, timeout=60, label="upload-confirmation")

            if done_sel:
                _log("info", "✅ Upload confirmed by YouTube")
            else:
                _log("warning", "⚠️  Upload confirmation not detected — video may still be processing")

            msg = f"{'Short' if upload_type == 'short' else 'Video'} uploaded successfully"
            _status("success", msg)
            return {"success": True, "message": msg}

        except Exception as e:
            import traceback
            _log("error", traceback.format_exc())
            return {"success": False, "message": str(e), "error_type": type(e).__name__}
