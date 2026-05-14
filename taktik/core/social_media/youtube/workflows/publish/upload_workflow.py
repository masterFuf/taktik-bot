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

Sélecteurs établis à partir des UI dumps réels (Nokia 4.2, Android 11, YouTube app) :
  - Create button : content-desc="Create" dans pivot_bar
  - Permission : com.android.permissioncontroller:id/permission_allow_foreground_only_button
  - "Add from gallery" : text="Add from gallery"
  - Gallery first item : premier ImageView clickable dans la vue galerie
  - Title/caption input : premier EditText available sur l'écran d'édition
  - Upload/Post button : text="Upload video" | "Upload Short" | "Post" | "UPLOAD"
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

try:
    from bridges.common.ipc import IPC as _IPC
    _ipc = _IPC()
except Exception:
    class _FallbackIPC:  # type: ignore
        def log(self, level, msg): logger.info(msg)
        def status(self, s, m=""): logger.info(f"[{s}] {m}")
    _ipc = _FallbackIPC()

_YOUTUBE_PKG = "com.google.android.youtube"

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


# ---------------------------------------------------------------------------
# Selectors (from real UI dumps)
# ---------------------------------------------------------------------------

# Bottom nav "Create" button
_CREATE_BTN = [
    '//*[@content-desc="Create"]',
    '//*[contains(@content-desc, "Créer")]',
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/pivot_bar"]//android.widget.Button',
]

# Upload mode selector (tabs: Video / Short / Live / Post)
_TAB_SHORT = [
    '//android.widget.TextView[@text="Short"]',
    '//android.widget.Button[@text="Short"]',
    '//*[contains(@content-desc, "Short")]',
]
_TAB_VIDEO = [
    '//android.widget.TextView[@text="Video"]',
    '//android.widget.Button[@text="Video"]',
    '//android.widget.TextView[@text="Vidéo"]',
    '//android.widget.Button[@text="Vidéo"]',
    '//*[contains(@content-desc, "Video")]',
    '//*[contains(@content-desc, "Vidéo")]',
]

# "Add from gallery" button on the upload screen
# Nokia / older UI : text "Add from gallery"
# Samsung / newer UI (Shorts camera view) : resource-id reel_camera_gallery_button_delegate
#                                            content-desc "Import video from photo library"
#                                            label text "Add"
_ADD_FROM_GALLERY = [
    # Shorts camera view — resource-id (device-agnostic, most reliable)
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/reel_camera_gallery_button_delegate"]',
    # content-desc (EN)
    '//*[@content-desc="Import video from photo library"]',
    '//*[@content-desc="Import video from gallery"]',
    # content-desc (FR) — variants seen on A80Pro and other devices
    '//*[@content-desc="Importer une vidéo de la galerie"]',
    '//*[@content-desc="Importer une vidéo depuis la photothèque"]',
    '//*[@content-desc="Importer une vidéo"]',
    # Classic upload screen text (older YouTube, Nokia-style)
    '//android.widget.Button[contains(@text, "Add from gallery")]',
    '//*[contains(@text, "Add from gallery")]',
    '//*[contains(@text, "Ajouter depuis la galerie")]',
    '//*[contains(@text, "Ajouter depuis")]',
    '//*[contains(@text, "Gallery")]',
    '//*[contains(@text, "Galerie")]',
]

# Gallery — first video item (most recent = just pushed)
_GALLERY_FIRST = [
    # Samsung/YouTube internal gallery — clickable FrameLayout wrappers (no resource-id)
    '(//android.widget.GridView//android.widget.FrameLayout[@clickable="true"])[1]',
    '(//android.widget.RecyclerView//android.widget.FrameLayout[@clickable="true"])[1]',
    # Fallback: ImageView inside GridView (uiautomator2 taps parent's bounds)
    '(//android.widget.GridView//android.widget.ImageView)[1]',
    '(//android.widget.RecyclerView//android.widget.ImageView)[1]',
    # System photo picker (Android 13+)
    '(//android.widget.GridView//android.view.View[@clickable="true"])[1]',
    '(//android.widget.RecyclerView//android.view.View[@clickable="true"])[1]',
]

# "Next" / "OK" / "Continue" after gallery selection, trimming screen, editor screen, etc.
# Ordered by specificity (resource-id first, then content-desc, then text).
_NEXT_BTN = [
    # Samsung YouTube — gallery multi-select Next button
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/multi_select_next_button"]',
    # Shorts camera view with loaded video — checkmark "Go to editor" (bottom right)
    # Appears after: gallery selection → trim OK → back on camera view
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/shorts_camera_next_button_delegate"]',
    # Shorts trim screen "OK" button (confirms trim selection)
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/shorts_trim_finish_trim_button"]',
    # Shorts editor screen bottom-right "Next" / "Suivant" button
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/shorts_post_bottom_button"]',
    # Trimming screen generic "creation next" (older YouTube versions)
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/creation_next_button"]',
    # Other next/continue resource-ids
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/next_button"]',
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/action_next"]',
    # content-desc variants (EN + FR)
    '//*[@content-desc="Go to editor"]',
    '//*[@content-desc="Accéder à l\'éditeur"]',
    '//*[@content-desc="Add segment to project"]',
    '//*[@content-desc="Ajouter le segment au projet"]',
    # text variants (EN)
    '//android.widget.Button[@text="OK"]',
    '//android.widget.Button[@text="Done"]',
    '//android.widget.Button[@text="Next"]',
    '//android.widget.Button[contains(@text, "Next")]',
    '//android.widget.Button[contains(@text, "Continue")]',
    '//android.widget.TextView[@text="Next"]',
    # text variants (FR)
    '//android.widget.Button[@text="Suivant"]',
    '//android.widget.Button[contains(@text, "Suivant")]',
    '//android.widget.Button[contains(@text, "Continuer")]',
]

# Title / caption input on the caption screen (Shorts: caption hint; Videos: title hint)
_TITLE_INPUT = [
    # EN hints
    '//android.widget.EditText[contains(@hint, "Add a title")]',
    '//android.widget.EditText[contains(@hint, "Add a caption")]',
    '//android.widget.EditText[contains(@hint, "Title")]',
    '//android.widget.EditText[contains(@hint, "Caption")]',
    '//android.widget.EditText[contains(@hint, "Add a description")]',
    '//android.widget.EditText[contains(@hint, "description")]',
    # FR hints — A80Pro confirmed: "Donnez un titre à votre Short"
    '//android.widget.EditText[contains(@hint, "Donnez un titre")]',
    '//android.widget.EditText[contains(@hint, "Ajouter un titre")]',
    '//android.widget.EditText[contains(@hint, "Ajouter une légende")]',
    '//android.widget.EditText[contains(@hint, "Titre")]',
    '//android.widget.EditText[contains(@hint, "Légende")]',
    '//android.widget.EditText[contains(@hint, "Ajouter une description")]',
    # Last resort: first tappable EditText on the screen
    '(//android.widget.EditText[@clickable="true"])[1]',
]

# Final upload / post button (EN + FR)
_UPLOAD_BTN = [
    # resource-id (most reliable) — confirmed on A80Pro French YouTube Shorts
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/upload_bottom_button"]',
    # EN text variants
    '//android.widget.Button[@text="Upload video"]',
    '//android.widget.Button[@text="Upload Short"]',
    '//android.widget.Button[@text="Upload"]',
    '//android.widget.Button[contains(@text, "Upload")]',
    '//android.widget.Button[contains(@text, "UPLOAD")]',
    '//android.widget.Button[@text="Post"]',
    # FR text variants — "Mettre en ligne le Short" confirmed on A80Pro
    '//android.widget.Button[@text="Mettre en ligne la vidéo"]',
    '//android.widget.Button[@text="Mettre en ligne le Short"]',
    '//android.widget.Button[contains(@text, "Mettre en ligne")]',
    '//android.widget.Button[@text="Publier"]',
    '//android.widget.Button[contains(@text, "Publier")]',
]

# Upload confirmation (post-upload snackbar/message) — EN + FR
_UPLOAD_DONE = [
    # resource-id (confirmed A80Pro FR): "Importée sur votre chaîne"
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/message"]',
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/action"]',  # "Voir la vidéo" link
    # FR text
    '//*[contains(@text, "Importée sur votre chaîne")]',
    '//*[contains(@text, "Importée")]',
    '//*[contains(@text, "Voir la vidéo")]',
    '//*[contains(@text, "Votre vidéo sera en ligne")]',
    # EN text
    '//*[contains(@text, "Your video will be live")]',
    '//*[contains(@text, "Your Short will be live")]',
    '//*[contains(@text, "Processing")]',
    '//*[contains(@text, "Uploading")]',
    '//*[contains(@text, "Uploaded")]',
    '//*[contains(@text, "published")]',
    '//*[contains(@text, "publié")]',
]

# Visibility options on the "Définir la visibilité" sub-screen.
# YouTube standard order: Public (1st), Non-listé/Unlisted (2nd), Privé/Private (3rd).
# The rows have no accessible text — we use ordered XPath within the scroll container.
_VISIBILITY_ROW = {
    "public":   "(//android.widget.ScrollView//android.view.ViewGroup[@clickable=\"true\"])[2]",
    "unlisted": "(//android.widget.ScrollView//android.view.ViewGroup[@clickable=\"true\"])[3]",
    "private":  "(//android.widget.ScrollView//android.view.ViewGroup[@clickable=\"true\"])[4]",
}

# Row on the details screen that opens the visibility sub-screen.
# Use single-slash `/` (direct children of RecyclerView > outer ViewGroup) to avoid
# counting the nested clickable ViewGroups inside the title row.
_DETAIL_ROW_DESCRIPTION = [
    # Text-based: find the clickable row that contains "Description" text
    '//android.view.ViewGroup[@clickable="true"][.//*[contains(@text, "Description") or contains(@text, "description") or contains(@text, "Décrip")]]',
    # Outer direct clickable children of RecyclerView (row-level, not inner sub-elements)
    '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup[@clickable="true"])[1]',
    '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup/android.view.ViewGroup[@clickable="true"])[1]',
]
_DETAIL_ROW_VISIBILITY = [
    # Text-based: most reliable — the row shows the current visibility value
    '//android.view.ViewGroup[@clickable="true"][.//*[contains(@text, "Visibilit") or contains(@text, "Visibility")]]',
    '//android.view.ViewGroup[@clickable="true"][.//*[contains(@text, "Priv") and not(contains(@text, "Description"))]]',
    '//android.view.ViewGroup[@clickable="true"][.//*[contains(@text, "Non list") or contains(@text, "Unlisted")]]',
    '//android.view.ViewGroup[@clickable="true"][.//*[contains(@text, "Publique") or contains(@text, "Public")]]',
    # Content-desc (some YouTube versions)
    '//*[contains(@content-desc, "visibilit")]',
    '//*[contains(@content-desc, "Visibility")]',
    # Outer direct clickable rows of RecyclerView (no inner-child nesting)
    # Based on dump: description=[1], visibility=[2] at this level
    '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup[@clickable="true"])[2]',
    '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup[@clickable="true"])[3]',
    '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup[@clickable="true"])[4]',
    # Nested (higher indices to skip title-row inner sub-elements at [1][2])
    '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup/android.view.ViewGroup[@clickable="true"])[4]',
    '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup/android.view.ViewGroup[@clickable="true"])[5]',
    '(//android.support.v7.widget.RecyclerView/android.view.ViewGroup/android.view.ViewGroup[@clickable="true"])[6]',
]
# Indicator that we've landed on the visibility sub-screen
_VISIBILITY_SCREEN_INDICATOR = [
    '//android.widget.ScrollView//android.view.ViewGroup[@clickable="true"]',
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/accessibility_layer_container"]',
]
# Audience/kids sub-screen detector — if present we opened the WRONG row
_AUDIENCE_SCREEN_INDICATOR = [
    '//*[@content-desc="En savoir plus"]',
    '//*[contains(@content-desc, "savoir plus")]',
    '//*[contains(@content-desc, "Learn more")]',
    '//*[contains(@content-desc, "learn more")]',
]
# Description sub-screen EditText (full-screen, no hint, becomes focused)
_DESCRIPTION_EDITTEXT = [
    '//android.widget.EditText[@clickable="true"]',
]


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

            # ── Step 2: open YouTube ─────────────────────────────────────────
            _status("running", "Opening YouTube…")
            # Force-stop first so we always start from a clean state
            # (handles cases where a previous run crashed mid-flow)
            d.shell(f"am force-stop {_YOUTUBE_PKG}")
            time.sleep(0.8)
            # Use monkey to launch — am start with hardcoded activity path fails silently
            d.shell(f"monkey -p {_YOUTUBE_PKG} -c android.intent.category.LAUNCHER 1")
            # Wait up to 6 s for YouTube to appear in the foreground
            deadline = time.time() + 6
            launched = False
            while time.time() < deadline:
                fg = d.shell("dumpsys window | grep mCurrentFocus").output or ""
                if _YOUTUBE_PKG in fg:
                    launched = True
                    break
                time.sleep(0.5)
            if not launched:
                # Fallback: am start intent
                d.shell(f"am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n {_YOUTUBE_PKG}/.app.honeycomb.Shell$HomeActivity")
                time.sleep(3)
            else:
                time.sleep(1.5)

            # Make sure we're on home (not a watch page)
            _try_tap(d, ['//*[@content-desc="Home"]', '//*[@content-desc="Accueil"]'], timeout=2, label="nav-home")
            time.sleep(1)

            # ── Dismiss notification permission popup if present ──────────────
            # 1) System permission dialog (com.android.permissioncontroller)
            # 2) In-app YouTube dialog ("Activer les notifications" / "Enable notifications")
            _yt_notif_cancel = [
                f'//*[@resource-id="{_YOUTUBE_PKG}:id/custom_confirm_dialog_cancel_button"]',
            ]
            if self._perms.deny_if_present(wait=3.0) or _try_tap(d, _yt_notif_cancel, timeout=2, label="notif-cancel"):
                _log("info", "🔕 Dismissed notification permission popup")
                time.sleep(0.8)

            # ── Step 3: tap Create "+" ───────────────────────────────────────
            _status("running", "Tapping Create button…")
            if not _try_tap(d, _CREATE_BTN, timeout=5, label="create-btn"):
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
                _try_tap(d, _TAB_SHORT, timeout=3, label="tab-short")
            else:
                _try_tap(d, _TAB_VIDEO, timeout=3, label="tab-video")
            time.sleep(0.8)

            # ── Step 6: tap "Add from gallery" ──────────────────────────────
            _status("running", "Opening gallery…")
            if not _try_tap(d, _ADD_FROM_GALLERY, timeout=6, label="add-from-gallery"):
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
            if not _try_tap(d, _GALLERY_FIRST, timeout=8, label="gallery-first"):
                return {"success": False, "message": "Could not select first item in gallery"}
            time.sleep(2)

            # ── Step 9: tap Next (may be needed multiple times) ──────────────
            # Flow varies by device/YouTube version:
            #   Samsung:  gallery → multi-select Next → trimming → caption
            #   A80Pro:   gallery → trim screen (OK) → camera+video → checkmark → caption
            # Up to 6 rounds to cover all intermediate screens.
            _status("running", "Navigating to edit screen…")
            for i in range(6):
                if _wait_for_any(d, _TITLE_INPUT, timeout=3, label=f"title-input-check-{i+1}"):
                    break  # Already on caption/title screen
                _log("debug", f"📍 Step 9 round {i+1}/6 — tapping next")
                _try_tap(d, _NEXT_BTN, timeout=4, label=f"next-btn-{i+1}")
                time.sleep(2.5)  # transitions can be slow

            # ── Step 10: enter title ──────────────────────────────────────────
            if title:
                _status("running", "Entering title…")
                _log("info", f"✏️  Title: {title[:60]}")
                found_title_sel = _wait_for_any(d, _TITLE_INPUT, timeout=5, label="title-input-tap")
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
                if _try_tap(d, _DETAIL_ROW_DESCRIPTION, timeout=3, label="desc-row"):
                    time.sleep(1)  # wait for sub-screen animation
                    if _wait_for_any(d, _DESCRIPTION_EDITTEXT, timeout=4, label="desc-edittext"):
                        # Click field first, then type — same pattern as Instagram
                        try:
                            d.xpath(_DESCRIPTION_EDITTEXT[0]).click()
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
            for vis_candidate in _DETAIL_ROW_VISIBILITY:
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
                time.sleep(1)  # wait for sub-screen animation
                # Detect if we accidentally opened the audience/kids screen
                on_wrong_screen = any(
                    d.xpath(s).exists for s in _AUDIENCE_SCREEN_INDICATOR
                )
                if on_wrong_screen:
                    _log("warning", "⚠️  Opened audience/kids screen (wrong row) — pressing back, trying next")
                    d.press("back")
                    time.sleep(1.5)  # wait for RecyclerView to re-render
                    continue
                # Check we're on the correct visibility sub-screen
                if _wait_for_any(d, _VISIBILITY_SCREEN_INDICATOR, timeout=4, label="visibility-screen"):
                    vis_sel = _VISIBILITY_ROW.get(vis)
                    if vis_sel and _try_tap(d, [vis_sel], timeout=4, label=f"visibility-{vis}"):
                        _log("info", f"✅ Visibility set to {vis}")
                        vis_set = True
                        time.sleep(0.5)
                        d.press("back")  # return to details
                        time.sleep(1)
                    else:
                        _log("warning", f"⚠️  Could not find {vis} option — leaving default")
                        d.press("back")
                        time.sleep(0.5)
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
            if not _try_tap(d, _UPLOAD_BTN, timeout=8, label="upload-btn"):
                return {"success": False, "message": "Could not find Upload/Post button"}

            # ── Step 13: wait for confirmation ───────────────────────────────
            _status("running", "Waiting for upload confirmation…")
            done_sel = _wait_for_any(d, _UPLOAD_DONE, timeout=60, label="upload-confirmation")

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
