"""
Instagram POST publish workflow.
=================================
Publie une photo/video unique en POST de feed depuis un fichier local.

Le flux reproduit, etape par etape, la sequence validee dans le Cartography Lab
(selector-only, AUCUNE coordonnee codee en dur) :

  1. Pousse le fichier via ADB + indexe la MediaStore (helper partage media_store).
  2. Lance Instagram (clone-aware) et revient au feed.
  3. Ouvre l'ecran de creation ("+").
  4. Ferme la modale brouillon "Keep editing your draft?" si presente (optionnel).
  5. Selectionne le premier media de la galerie (le plus recent = celui pousse).
  6. Tape "Next" jusqu'a l'ecran composer (champ caption present).
  7. Saisit la caption + hashtags.
  8. Tape "Share".
  9. Attend la fermeture du composer (commit du partage).

Tous les selecteurs viennent de
`taktik/core/social_media/instagram/ui/selectors/surfaces/content_creation.py`.
Le bridge `bridges/instagram/publish/runtime/bridge.py` n'est qu'un adaptateur
(connexion device -> ce workflow -> evenements JSON).
"""

from __future__ import annotations

import os
import time
from typing import Callable, List, Optional

from loguru import logger

from taktik.core.clone import get_active_package
from taktik.core.shared.device.media_store import (
    push_media,
    scan_wait_for,
    trigger_media_scan,
)
from taktik.core.social_media.instagram.ui.selectors.surfaces.content_creation import (
    CONTENT_CREATION_SELECTORS as CC,
)


# ---------------------------------------------------------------------------
# IPC fallbacks
# ---------------------------------------------------------------------------

def _default_log(level: str, message: str) -> None:
    getattr(logger, level if hasattr(logger, level) else "info")(message)


def _default_status(status: str, message: str = "") -> None:
    logger.info(f"[{status}] {message}")


class InstagramPostWorkflow:
    """Publie un media unique en POST de feed Instagram.

    Parameters
    ----------
    device       : objet device uiautomator2 (ConnectionService.device)
    device_id    : serial ADB
    log          : callback (level, message) -> emis vers la console debug du desktop
    status       : callback (status, message) -> mise a jour d'etat
    package_name : package Instagram (clone) cible ; defaut = package actif
    """

    def __init__(
        self,
        device,
        device_id: str,
        *,
        log: Optional[Callable[[str, str], None]] = None,
        status: Optional[Callable[[str, str], None]] = None,
        package_name: Optional[str] = None,
    ):
        self.device = device
        self.device_id = device_id
        self._log = log or _default_log
        self._status = status or _default_status
        self.package_name = package_name or get_active_package()
        self._a = self._build_actions(device)

    # ------------------------------------------------------------------
    # Action bundle (same atomic facades the Cartography Lab validated with)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_actions(device) -> dict:
        from taktik.core.social_media.instagram.actions.atomic.interaction import ClickActions
        from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
        from taktik.core.social_media.instagram.actions.atomic.text import TextActions
        from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade

        facade = DeviceFacade(device)
        return {
            "click": ClickActions(facade),
            "nav": NavigationActions(facade),
            "kb": TextActions(facade),
        }

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    def execute(
        self,
        caption: str = "",
        hashtags: Optional[List[str]] = None,
        media_paths: Optional[List[str]] = None,
    ) -> dict:
        """Publie le premier media de `media_paths` en POST.

        Returns dict {success: bool, message: str, error_type: str | None}.
        """
        hashtags = hashtags or []
        media_paths = media_paths or []

        if not media_paths:
            return self._error("no_media", "At least one media path is required")
        local_path = media_paths[0]
        if not os.path.isfile(local_path):
            return self._error("file_not_found", f"File not found: {local_path}")

        # 1. Push + MediaStore indexing (shared helper)
        self._status("uploading", f"Pushing media: {os.path.basename(local_path)}")
        remote_path = push_media(self.device_id, local_path)
        if not remote_path:
            return self._error("push_failed", "Failed to push media to device")
        trigger_media_scan(self.device_id, remote_path, local_path, log=self._log)
        time.sleep(scan_wait_for(local_path))

        # 2. Launch Instagram + return to feed
        self._status("navigating", "Opening Instagram...")
        self._launch_app()
        try:
            if not self._a["nav"].navigate_to_home():
                self._log("warning", "navigate_to_home returned False (continuing)")
        except Exception as e:
            self._log("warning", f"navigate_to_home raised (non-fatal): {e}")
        time.sleep(1.0)

        # 3. Open the creation screen ("+")
        self._status("navigating", "Opening creation...")
        if not self._tap(CC.create_button_flow_xpaths(), timeout=6):
            return self._error("create_not_found", "Create button not found")
        time.sleep(1.2)

        # 4. Dismiss the "Keep editing your draft?" modal if present (optional)
        if self._tap(CC.draft_dismiss_xpaths(), timeout=2):
            self._log("info", "Dismissed draft modal (Start new video)")
            time.sleep(0.8)

        # 5. Select the first gallery item (most recent = the pushed file)
        self._status("selecting", "Selecting media from gallery...")
        if not self._tap(CC.first_gallery_item_xpath(), timeout=6):
            return self._error("gallery_item_not_found", "Could not select media from gallery")
        time.sleep(1.0)

        # 6. Tap "Next" until the caption composer is reached
        self._status("navigating", "Navigating to caption screen...")
        if not self._advance_to_composer():
            return self._error("composer_not_reached", "Caption screen was not reached")

        # 7. Enter caption + hashtags
        full_caption = self._build_caption(caption, hashtags)
        if full_caption:
            self._status("filling", "Entering caption...")
            if not self._fill_caption(full_caption):
                return self._error("caption_fill_failed", "Could not enter caption")
            time.sleep(0.5)

        # 8. Share. The IME may still cover the footer Share button after caption entry,
        # so dismiss the keyboard and retry once if the first tap misses.
        self._status("publishing", "Publishing...")
        if not self._tap(CC.share_button_xpaths(), timeout=6):
            self._dismiss_keyboard()
            if not self._tap(CC.share_button_xpaths(), timeout=6):
                return self._error("share_not_found", "Share button not found")

        # 9. Wait for the composer to close (publish committed)
        if not self._wait_for_publish_commit():
            return self._error(
                "publish_not_committed",
                "Instagram did not appear to finish publishing before timeout",
            )

        self._status("success", "Post published successfully")
        self._log("info", "Instagram post published")
        return {"success": True, "message": "Post published successfully", "error_type": None}

    # ------------------------------------------------------------------
    # Stage helpers
    # ------------------------------------------------------------------

    def _advance_to_composer(self, max_taps: int = 3) -> bool:
        """Tap Next (dismissing optional OK modals) until the caption field appears."""
        composer = CC.composer_xpaths()
        next_selectors = CC.next_button_xpaths()
        for _ in range(max_taps):
            if self._a["click"]._is_element_present(composer):
                return True
            # Optional post-selection modal ("OK")
            self._tap(CC.post_selection_ok_xpaths(), timeout=1)
            if not self._tap(next_selectors, timeout=4):
                self._log("debug", "No Next button on this screen")
            time.sleep(1.0)
        return self._a["click"]._is_element_present(composer)

    def _fill_caption(self, text: str) -> bool:
        if not self._tap(CC.composer_xpaths(), timeout=5):
            self._log("warning", "Caption field not focusable")
            return False
        time.sleep(0.4)
        try:
            typed = bool(self._a["kb"].type_text(text, clear_first=False, human_typing=True))
        except Exception as e:
            self._log("warning", f"type_text failed: {e}")
            return False
        # The keyboard hides the footer Share button — close it before publishing.
        self._dismiss_keyboard()
        return typed

    def _dismiss_keyboard(self) -> None:
        """Press back once to close the soft keyboard (keeps the composer open)."""
        try:
            self.device.press("back")
            time.sleep(0.5)
        except Exception as e:
            self._log("debug", f"keyboard dismiss skipped: {e}")

    def _wait_for_publish_commit(self, timeout: float = 120.0) -> bool:
        """Publish is committed once the composer (caption field) disappears."""
        composer = CC.composer_xpaths()
        start = time.time()
        while time.time() - start < timeout:
            if not self._a["click"]._is_element_present(composer):
                # settle so an upload progress screen can take over
                time.sleep(1.5)
                return True
            time.sleep(2.0)
        return False

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    def _launch_app(self) -> None:
        """Launch Instagram (clone-aware), mirroring AppManagementMixin._open_instagram."""
        pkg = self.package_name
        try:
            if pkg.startswith("com.taktik."):
                self.device.shell(
                    ["am", "start", "-n", f"{pkg}/com.instagram.mainactivity.LauncherActivity"]
                )
            else:
                self.device.app_start(pkg)
        except Exception as e:
            self._log("warning", f"App launch failed (non-fatal): {e}")
        time.sleep(3.0)

    def _tap(self, selectors, timeout: float = 4.0) -> bool:
        return bool(self._a["click"]._find_and_click(selectors, timeout=timeout))

    @staticmethod
    def _build_caption(caption: str, hashtags: List[str]) -> str:
        parts: List[str] = []
        caption = (caption or "").strip()
        if caption:
            parts.append(caption)
        tags = [f"#{str(t).lstrip('#').strip()}" for t in (hashtags or []) if str(t).strip()]
        if tags:
            parts.append(" ".join(tags))
        return "\n".join(parts)

    def _error(self, error_type: str, message: str) -> dict:
        self._log("error", message)
        return {"success": False, "message": message, "error_type": error_type}
