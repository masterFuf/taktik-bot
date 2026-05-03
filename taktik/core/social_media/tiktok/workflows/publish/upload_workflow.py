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
import re as _re
from typing import Optional

from loguru import logger

from taktik.core.shared.device.media_store import (
    push_media,
    trigger_media_scan,
    scan_wait_for,
)

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

# Bouton "Create" (bottom nav)
# Trouvé dans le dump : android.widget.Button id=com.zhiliaoapp.musically:id/nc_ content-desc='Create'
_CREATE_BTN = [
    '//*[@resource-id="com.zhiliaoapp.musically:id/nc_"]',
    '//*[@content-desc="Create"]',
    '//*[contains(@content-desc, "Créer")]',
    '//*[contains(@content-desc, "Create")]',
    '//*[@resource-id="com.zhiliaoapp.musically:id/mkn"]',
]

# Bouton "Upload/Gallery" dans le panneau de création (vue caméra)
# Trouvé : com.zhiliaoapp.musically:id/cl2 (FrameLayout clickable, bas-droit du panneau)
# La galerie thumbnail RecyclerView (t9w) est aussi une option
_UPLOAD_BTN = [
    '//*[@resource-id="com.zhiliaoapp.musically:id/cl2"]',
    '//*[@content-desc="Upload"]',
    '//*[contains(@content-desc, "Upload")]',
    '//*[@text="Upload"]',
    '//*[contains(@text, "Upload")]',
    '//*[contains(@text, "Importer")]',
    '//*[contains(@text, "Gallery")]',
    '//*[contains(@text, "Galerie")]',
]

# Dialog permission : "Allow TikTok to access photos and media"
# resource-id : com.android.permissioncontroller:id/permission_allow_button
_PERMISSION_ALLOW_BTN = [
    '//*[@resource-id="com.android.permissioncontroller:id/permission_allow_button"]',
    '//android.widget.Button[@text="ALLOW"]',
    '//android.widget.Button[contains(@text, "Allow")]',
    '//android.widget.Button[contains(@text, "Autoriser")]',
    '//android.widget.Button[contains(@text, "Toujours autoriser")]',
    '//android.widget.Button[@text="While using the app"]',
]

# Écran galerie — premier élément (fichier le plus récent)
# Dump réel (TikTok 44.9) :
#   GridView rid=ir_  (galerie plein écran modal)
#   ImageView rid=nm8  (miniature de chaque item — premier = le plus récent)
#   Bounds premier item : [4,231][239,469] sur écran 720×1430
# Note: nm8 n'est pas marqué clickable=true mais uiautomator2 peut le tapper
_GALLERY_FIRST_ITEM = [
    '(//android.widget.ImageView[@resource-id="com.zhiliaoapp.musically:id/nm8"])[1]',
    '(//android.widget.GridView[@resource-id="com.zhiliaoapp.musically:id/ir_"]//android.widget.ImageView)[1]',
    '//*[@resource-id="com.zhiliaoapp.musically:id/ir_"]//*[@class="android.widget.ImageView"][1]',
]

# Bouton "Next" / "Suivant" (plusieurs écrans)
# Dump réel (TikTok 44.9) :
#   rid=ooo  text='Next'  → écran trim/preview après sélection galerie (DUMP2)
#   rid=w51  text='Next'  → barre bas de la galerie (mode multi-sélect, ck=false avant sélection)
_NEXT_BTN = [
    '//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/ooo"]',
    '//android.widget.Button[@resource-id="com.zhiliaoapp.musically:id/w51"]',
    '//android.widget.Button[@text="Next"]',
    '//android.widget.Button[contains(@text, "Next")]',
    '//android.widget.Button[contains(@text, "Suivant")]',
    '//android.widget.TextView[contains(@text, "Next")]',
    '//android.widget.TextView[contains(@text, "Suivant")]',
    '//*[@resource-id="com.zhiliaoapp.musically:id/next_btn"]',
]

# Zone de description / caption
_CAPTION_INPUT = [
    '//android.widget.EditText[contains(@hint, "description")]',
    '//android.widget.EditText[contains(@hint, "Description")]',
    '//android.widget.EditText[contains(@content-desc, "Description")]',
    '//android.widget.EditText[contains(@hint, "caption")]',
    '//android.widget.EditText[@clickable="true"][1]',
    '(//android.widget.EditText)[1]',
]

# Bouton "Post" / "Publier"
_POST_BTN = [
    '//android.widget.Button[@content-desc="Post"]',
    '//android.widget.Button[contains(@content-desc, "Post")]',
    '//android.widget.Button[@text="Post"]',
    '//android.widget.Button[contains(@text, "Post")]',
    '//android.widget.Button[contains(@text, "Publier")]',
    '//android.widget.TextView[contains(@text, "Post")]',
    '//android.widget.TextView[contains(@text, "Publier")]',
    '//*[@resource-id="com.zhiliaoapp.musically:id/post_btn"]',
]

# Indicateur que le post a bien été publié
_SUCCESS_INDICATOR = [
    '//*[contains(@text, "successfully")]',
    '//*[contains(@text, "published")]',
    '//*[contains(@text, "publié")]',
    '//*[contains(@text, "succès")]',
    '//*[contains(@content-desc, "Posted")]',
]

# ── XPath lxml translator (identique au signup_workflow) ─────────────────────
_CLASS_STEP_RE = _re.compile(
    r'(/{1,2})([a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*)+)'
)

def _to_lxml(xp: str) -> str:
    return _CLASS_STEP_RE.sub(r'\1node[@class="\2"]', xp)


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
        hashtags = hashtags or []

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

        # 4. Force-stop TikTok so it rebuilds its gallery cache on fresh start
        # (if TikTok is already running, its gallery cache is stale and won't show the new file)
        tiktok_pkg = package_name or self._get_tiktok_package()
        _ipc.log("info", "🔄 Force-stopping TikTok to ensure fresh gallery cache...")
        self._adb_force_stop(tiktok_pkg)
        time.sleep(1.0)

        # 5. Open TikTok
        _ipc.log("info", "📱 Opening TikTok...")
        self.device.app_start(tiktok_pkg)
        time.sleep(3.0)  # Wait longer for TikTok to fully load + rebuild its gallery cache

        # 6. Appuyer sur le bouton Create
        _ipc.status("navigating", "Tapping Create button...")
        if not self._tap_create_button():
            return self._error("create_btn_not_found", "Create button not found")
        time.sleep(1.5)

        # 7. Taper le bouton Upload/Gallery dans le panneau de création caméra
        _ipc.status("navigating", "Tapping Upload/Gallery button...")
        if not self._tap_upload():
            return self._error("upload_btn_not_found", "Upload button not found in creation panel")
        time.sleep(1.5)

        # 7b. Gérer la dialog de permission (accès aux photos)
        self._handle_permission_dialog()
        time.sleep(2.0)

        # 7c. Pull-to-refresh the gallery so MediaStore changes are visible
        self._refresh_tiktok_gallery()
        time.sleep(1.0)

        # 8. Sélectionner le premier fichier de la galerie
        _ipc.status("selecting", "Selecting media from gallery...")
        if not self._select_first_gallery_item():
            return self._error("gallery_item_not_found", "Could not select media from gallery")
        time.sleep(2.0)

        # 8. Taper "Next" jusqu'à l'écran de description (max 3 fois)
        _ipc.status("navigating", "Navigating to post screen...")
        for _ in range(3):
            if self._is_on_post_screen():
                break
            if not self._tap(selectors=_NEXT_BTN, timeout=3.0):
                break
            time.sleep(1.5)

        # 9. Saisir la description
        full_caption = self._build_caption(caption, hashtags)
        if full_caption:
            _ipc.status("filling", "Entering caption...")
            self._fill_caption(full_caption)
            time.sleep(0.5)

        # 10. Taper "Post"
        _ipc.status("publishing", "Publishing...")
        if not self._tap(selectors=_POST_BTN, timeout=5.0):
            return self._error("post_btn_not_found", "Post button not found")

        time.sleep(3.0)

        # 11. Dismiss any system dialogs that may appear after posting
        # (e.g. Android "Add to Home Screen" / widget install prompt from TikTok)
        self._dismiss_post_popups()

        # 12. Vérification succès (best-effort)
        _ipc.status("success", "Post published successfully!")
        _ipc.log("info", "✅ TikTok post published")
        return {"success": True, "message": "Post published successfully", "error_type": None}

    # ------------------------------------------------------------------
    # ADB helpers
    # ------------------------------------------------------------------

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

    def _tap_create_button(self) -> bool:
        """Tap the Create button in the bottom navigation bar.
        
        In TikTok 44.9+: resource-id=nc_, content-desc='Create'
        Located at 40% from left in the bottom nav bar.
        """
        if self._tap(_CREATE_BTN, timeout=5.0):
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
        """Tap the Upload/Gallery button in the camera creation panel.
        
        In TikTok 44.9+, the upload button is the folder icon (cl2)
        at the bottom-right of the camera view, beside the gallery strip.
        Fallback: tap the gallery strip area directly.
        """
        if self._tap(_UPLOAD_BTN, timeout=6.0):
            return True
        # Fallback: tap the bottom-right area of the creation panel
        # (coordinate ~80% width, ~78% height — where cl2 is located)
        try:
            info = self.device.info
            w = info.get("displayWidth", 720)
            h = info.get("displayHeight", 1520)
            _ipc.log("debug", f"[upload] fallback coord tap: ({int(w*0.81)}, {int(h*0.80)})")
            self.device.click(int(w * 0.81), int(h * 0.80))
            return True
        except Exception as e:
            _ipc.log("error", f"[upload] fallback failed: {e}")
            return False

    def _handle_permission_dialog(self) -> bool:
        """Handle 'Allow TikTok to access photos and media' permission dialog.
        
        Returns True if a dialog was found and dismissed, False if none.
        """
        el = self._find_element(_PERMISSION_ALLOW_BTN, timeout=3.0)
        if el:
            try:
                _ipc.log("info", "🔓 Granting media access permission...")
                el.click()
                time.sleep(1.0)
                return True
            except Exception as e:
                _ipc.log("warning", f"Permission tap failed: {e}")
        return False

    def _dismiss_post_popups(self):
        """Dismiss any system or app dialogs that appear after posting.

        Known dialogs (TikTok 44.9 on Nokia 4.2 / Android 11):
          - "Add to Home Screen" (widget install) → Button text='CANCEL'
        """
        _CANCEL_BTNS = [
            '//android.widget.Button[@text="CANCEL"]',
            '//android.widget.Button[contains(@text, "Cancel")]',
            '//android.widget.Button[contains(@text, "Annuler")]',
            '//android.widget.Button[contains(@text, "Not now")]',
            '//android.widget.Button[contains(@text, "Non merci")]',
        ]
        el = self._find_element(_CANCEL_BTNS, timeout=3.0)
        if el:
            try:
                _ipc.log("info", "🚫 Dismissing post-publishing dialog...")
                el.click()
                time.sleep(0.5)
            except Exception as e:
                _ipc.log("debug", f"[dismiss_popup] click failed: {e}")

    def _refresh_tiktok_gallery(self):
        """Pull-to-refresh the TikTok gallery picker to pick up newly scanned media.
        
        Swipes down on the gallery grid area to trigger a refresh.
        This is needed when the file was added after the gallery was opened.
        """
        try:
            info = self.device.info
            w = info.get("displayWidth", 720)
            h = info.get("displayHeight", 1520)
            # Swipe down in the gallery area (top 60% of the screen, where image grid is)
            mid_x = w // 2
            start_y = int(h * 0.35)
            end_y = int(h * 0.60)
            _ipc.log("debug", f"[gallery] pull-to-refresh swipe ({mid_x},{start_y}) → ({mid_x},{end_y})")
            self.device.swipe(mid_x, start_y, mid_x, end_y, duration=0.4)
        except Exception as e:
            _ipc.log("debug", f"[gallery] refresh swipe skipped: {e}")

    def _select_first_gallery_item(self) -> bool:
        """
        Select the first (most recent) item in TikTok's gallery picker.
        Falls back to coordinate-based tap in the first grid cell.
        """
        if self._tap(_GALLERY_FIRST_ITEM, timeout=5.0):
            return True
        # Coordinate fallback: first item in gallery GridView
        # Based on real dump: nm8 bounds=[4,231][239,469] on 720×1430 → center=(122,350)
        # Relative: x≈17%, y≈24.5%
        try:
            info = self.device.info
            w = info.get("displayWidth", 720)
            h = info.get("displayHeight", 1430)
            tap_x = int(w * 0.17)
            tap_y = int(h * 0.245)
            _ipc.log("debug", f"[gallery] coord fallback tap: ({tap_x}, {tap_y})")
            self.device.click(tap_x, tap_y)
            return True
        except Exception:
            return False

    def _is_on_post_screen(self) -> bool:
        """Check if we're on the post description screen."""
        try:
            from lxml import etree
            xml = self.device.dump_hierarchy(compressed=False)
            tree = etree.fromstring(xml.encode("utf-8"))
            for xp in _POST_BTN + _CAPTION_INPUT:
                try:
                    if tree.xpath(_to_lxml(xp)):
                        return True
                except Exception:
                    pass
            return False
        except Exception:
            return False

    def _fill_caption(self, text: str):
        """Find the caption/description field and type the text."""
        el = self._find_element(_CAPTION_INPUT, timeout=5.0)
        if el:
            try:
                el.click()
                time.sleep(0.3)
                self.device.send_keys(text, clear=True)
                return
            except Exception:
                pass
        # Fallback: try clicking the visible text area by position
        try:
            info = self.device.info
            w = info.get("displayWidth", 576)
            h = info.get("displayHeight", 1280)
            self.device.click(w // 2, int(h * 0.35))
            time.sleep(0.3)
            self.device.send_keys(text, clear=True)
        except Exception as e:
            logger.warning(f"fill_caption fallback failed: {e}")

    # ------------------------------------------------------------------
    # uiautomator2 helpers
    # ------------------------------------------------------------------

    def _find_element(self, selectors: list, timeout: float = _EXIST_TIMEOUT):
        for xp in selectors:
            try:
                el = self.device.xpath(xp)
                if el.wait(timeout=timeout):
                    return el
            except Exception:
                continue
        return None

    def _tap(self, selectors: list, timeout: float = _EXIST_TIMEOUT) -> bool:
        el = self._find_element(selectors, timeout)
        if el:
            try:
                el.click()
                return True
            except Exception:
                pass
        return False

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    def _get_tiktok_package(self) -> str:
        """Return whichever TikTok package is installed on the device."""
        for pkg in ("com.zhiliaoapp.musically", "com.ss.android.ugc.trill",
                    "com.bytedance.trill"):
            try:
                result = subprocess.run(
                    ["adb", "-s", self.device_id, "shell", "pm", "list", "packages", pkg],
                    capture_output=True, text=True, timeout=10
                )
                if pkg in result.stdout:
                    return pkg
            except Exception:
                pass
        return "com.zhiliaoapp.musically"

    @staticmethod
    def _build_caption(caption: str, hashtags: list[str]) -> str:
        parts = []
        if caption:
            parts.append(caption)
        if hashtags:
            parts.append(" ".join(f"#{h.lstrip('#')}" for h in hashtags))
        return "\n".join(parts)

    @staticmethod
    def _error(error_type: str, message: str) -> dict:
        _ipc.log("error", f"❌ {message}")
        return {"success": False, "message": message, "error_type": error_type}
