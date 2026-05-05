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


def _try_tap(device, selectors: list[str], timeout: float = 3.0) -> bool:
    """Try a list of XPath selectors in order; return True on first success."""
    for sel in selectors:
        try:
            el = device.xpath(sel)
            if el.wait(timeout=timeout):
                el.click()
                return True
        except Exception:
            continue
    return False


def _wait_for_any(device, selectors: list[str], timeout: float = 10.0) -> Optional[str]:
    """Return the first selector that appears within timeout, else None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for sel in selectors:
            try:
                if device.xpath(sel).exists:
                    return sel
            except Exception:
                continue
        time.sleep(0.5)
    return None


# ---------------------------------------------------------------------------
# Selectors (from real UI dumps)
# ---------------------------------------------------------------------------

# Bottom nav "Create" button (content-desc="Create", android.widget.Button in pivot_bar)
_CREATE_BTN = [
    '//*[@content-desc="Create"]',
    '//*[contains(@content-desc, "Créer")]',
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/pivot_bar"]//android.widget.Button',
]

# Permission dialog : "Allow YouTube to take pictures and record video?"
# Prefer "WHILE USING THE APP" — keeps permission active for the session
_PERM_ALLOW_BTN = [
    '//*[@resource-id="com.android.permissioncontroller:id/permission_allow_foreground_only_button"]',
    '//*[@resource-id="com.android.permissioncontroller:id/permission_allow_one_time_button"]',
    '//android.widget.Button[contains(@text, "WHILE USING")]',
    '//android.widget.Button[contains(@text, "While using")]',
    '//android.widget.Button[contains(@text, "Allow")]',
    '//android.widget.Button[contains(@text, "Autoriser")]',
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
    '//*[contains(@content-desc, "Video")]',
]

# "Add from gallery" button on the upload screen
# Nokia / older UI : text "Add from gallery"
# Samsung / newer UI (Shorts camera view) : resource-id reel_camera_gallery_button_delegate
#                                            content-desc "Import video from photo library"
#                                            label text "Add"
_ADD_FROM_GALLERY = [
    # Shorts camera view (Samsung, newer YouTube)
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/reel_camera_gallery_button_delegate"]',
    f'//*[@content-desc="Import video from photo library"]',
    f'//*[@content-desc="Importer une vidéo depuis la photothèque"]',
    # Classic upload screen (Nokia, older YouTube)
    '//android.widget.Button[contains(@text, "Add from gallery")]',
    '//*[contains(@text, "Add from gallery")]',
    '//*[contains(@text, "Ajouter depuis")]',
    '//*[contains(@text, "Galerie")]',
    '//*[contains(@text, "Gallery")]',
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

# "Next" / "Continue" after gallery selection and after trimming screen
_NEXT_BTN = [
    # Samsung YouTube — gallery multi-select Next button
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/multi_select_next_button"]',
    # Trimming screen "Done" button (content-desc="Add segment to project")
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/creation_next_button"]',
    # Other next/continue resource-ids
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/next_button"]',
    f'//*[@resource-id="{_YOUTUBE_PKG}:id/action_next"]',
    '//android.widget.Button[@text="Done"]',
    '//android.widget.Button[@text="Next"]',
    '//android.widget.Button[contains(@text, "Next")]',
    '//android.widget.Button[contains(@text, "Suivant")]',
    '//android.widget.Button[contains(@text, "Continue")]',
    '//android.widget.TextView[@text="Next"]',
]

# Title / caption input on the edit screen (Shorts use "caption" hint)
_TITLE_INPUT = [
    '//android.widget.EditText[contains(@hint, "Add a title")]',
    '//android.widget.EditText[contains(@hint, "Add a caption")]',
    '//android.widget.EditText[contains(@hint, "Title")]',
    '//android.widget.EditText[contains(@hint, "Caption")]',
    '//android.widget.EditText[contains(@hint, "Titre")]',
    '//android.widget.EditText[contains(@hint, "Légende")]',
    '//android.widget.EditText[contains(@hint, "description")]',
    '//android.widget.EditText[contains(@hint, "Add a description")]',
    '(//android.widget.EditText[@clickable="true"])[1]',
]

# Final upload / post button
_UPLOAD_BTN = [
    '//android.widget.Button[@text="Upload video"]',
    '//android.widget.Button[@text="Upload Short"]',
    '//android.widget.Button[contains(@text, "Upload")]',
    '//android.widget.Button[@text="Post"]',
    '//android.widget.Button[contains(@text, "Publier")]',
    '//android.widget.Button[contains(@text, "UPLOAD")]',
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(
        self,
        local_path: str,
        title: str = "",
        description: str = "",
        upload_type: str = "short",   # "short" | "video"
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
            _try_tap(d, ['//*[@content-desc="Home"]', '//*[@content-desc="Accueil"]'], timeout=2)
            time.sleep(1)

            # ── Dismiss notification permission popup if present ──────────────
            # 1) System permission dialog (com.android.permissioncontroller)
            # 2) In-app YouTube dialog ("Activer les notifications" / "Enable notifications")
            _notif_deny = [
                '//*[@resource-id="com.android.permissioncontroller:id/permission_deny_button"]',
                f'//*[@resource-id="{_YOUTUBE_PKG}:id/custom_confirm_dialog_cancel_button"]',
                '//android.widget.Button[contains(@text, "Ne pas autoriser")]',
                '//android.widget.Button[contains(@text, "Non merci")]',
                '//android.widget.Button[contains(@text, "No thanks")]',
                '//android.widget.Button[contains(@text, "Don\'t allow")]',
            ]
            if _try_tap(d, _notif_deny, timeout=3):
                _log("info", "🔕 Dismissed notification permission popup")
                time.sleep(0.8)

            # ── Step 3: tap Create "+" ───────────────────────────────────────
            _status("running", "Tapping Create button…")
            if not _try_tap(d, _CREATE_BTN, timeout=5):
                return {"success": False, "message": "Could not find Create (+) button"}
            time.sleep(1.5)

            # ── Step 4: dismiss permission dialog if present ─────────────────
            _status("running", "Checking permissions…")
            # Grant any permission dialogs that appear after tapping Create
            # (camera, microphone — loop up to 3 times for chained dialogs)
            for _perm_round in range(3):
                perm_detected = _wait_for_any(d, [
                    '//*[@resource-id="com.android.permissioncontroller:id/grant_dialog"]',
                    '//*[@resource-id="com.android.permissioncontroller:id/permission_allow_foreground_only_button"]',
                    '//*[@resource-id="com.android.permissioncontroller:id/permission_allow_button"]',
                    '//*[@resource-id="com.android.permissioncontroller:id/permission_allow_one_time_button"]',
                ], timeout=2 if _perm_round > 0 else 4)
                if not perm_detected:
                    break
                _log("info", f"🔐 Permission dialog #{_perm_round + 1} — granting access")
                if not _try_tap(d, _PERM_ALLOW_BTN, timeout=4):
                    _log("warning", "⚠️  Could not tap Allow — trying to continue anyway")
                    break
                time.sleep(1)

            # ── Step 5: select tab (Short / Video) ──────────────────────────
            _status("running", f"Selecting upload type: {upload_type}…")
            if upload_type == "short":
                _try_tap(d, _TAB_SHORT, timeout=3)
            else:
                _try_tap(d, _TAB_VIDEO, timeout=3)
            time.sleep(0.8)

            # ── Step 6: tap "Add from gallery" ──────────────────────────────
            _status("running", "Opening gallery…")
            if not _try_tap(d, _ADD_FROM_GALLERY, timeout=6):
                return {"success": False, "message": "Could not find 'Add from gallery' button"}
            time.sleep(2)

            # ── Step 7: dismiss storage/media permission if it appears ───────
            media_perm_sel = _wait_for_any(d, [
                '//*[contains(@text, "Allow YouTube to access")]',
                '//*[contains(@text, "Allow access")]',
                '//*[@resource-id="com.android.permissioncontroller:id/grant_dialog"]',
            ], timeout=3)
            if media_perm_sel:
                _log("info", "🔐 Media permission dialog — granting access")
                _try_tap(d, _PERM_ALLOW_BTN + [
                    '//*[@resource-id="com.android.permissioncontroller:id/permission_allow_button"]',
                    '//android.widget.Button[contains(@text, "Allow")]',
                ], timeout=4)
                time.sleep(1.5)

            # ── Step 8: select first item in gallery ─────────────────────────
            _status("running", "Selecting video from gallery…")
            if not _try_tap(d, _GALLERY_FIRST, timeout=8):
                return {"success": False, "message": "Could not select first item in gallery"}
            time.sleep(2)

            # ── Step 9: tap Next (may be needed multiple times) ──────────────
            # Short flow: gallery → trimming screen (Next) → caption screen (Next)
            _status("running", "Navigating to edit screen…")
            for _ in range(4):
                if _wait_for_any(d, _TITLE_INPUT, timeout=3):
                    break  # Already on caption/title screen
                _try_tap(d, _NEXT_BTN, timeout=4)
                time.sleep(2.5)  # Samsung transitions can be slow

            # ── Step 10: enter title ──────────────────────────────────────────
            if title:
                _status("running", "Entering title…")
                _log("info", f"✏️  Title: {title[:60]}")
                if _try_tap(d, _TITLE_INPUT, timeout=5):
                    time.sleep(0.5)
                    d.xpath(_TITLE_INPUT[0]).set_text("")  # clear existing
                    d.send_keys(title)
                    time.sleep(0.5)
                else:
                    _log("warning", "⚠️  Could not find title input — skipping")

            # ── Step 11: enter description (if different from title) ──────────
            if description and description != title:
                _log("info", f"✏️  Description: {description[:80]}")
                desc_selectors = [
                    '//android.widget.EditText[contains(@hint, "description")]',
                    '//android.widget.EditText[contains(@hint, "Description")]',
                    '(//android.widget.EditText[@clickable="true"])[2]',
                ]
                if _try_tap(d, desc_selectors, timeout=3):
                    time.sleep(0.5)
                    d.send_keys(description)
                    time.sleep(0.5)

            # Dismiss keyboard
            try:
                d.press("back")
                time.sleep(0.5)
            except Exception:
                pass

            # ── Step 12: tap Upload / Post ────────────────────────────────────
            _status("running", "Uploading…")
            _log("info", "🚀 Tapping Upload / Post button")
            if not _try_tap(d, _UPLOAD_BTN, timeout=8):
                return {"success": False, "message": "Could not find Upload/Post button"}

            # ── Step 13: wait for confirmation ───────────────────────────────
            _status("running", "Waiting for upload confirmation…")
            done_sel = _wait_for_any(d, [
                '//*[contains(@text, "Your video will be live")]',
                '//*[contains(@text, "Your Short will be live")]',
                '//*[contains(@text, "Processing")]',
                '//*[contains(@text, "Uploading")]',
                '//*[contains(@text, "Uploaded")]',
                '//*[contains(@text, "published")]',
                '//*[contains(@text, "publié")]',
            ], timeout=20)

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
