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
        post_type: str = "post",
        story_via_feed: bool = False,
    ):
        self.device = device
        self.device_id = device_id
        self._log = log or _default_log
        self._status = status or _default_status
        self.package_name = package_name or get_active_package()
        # post | reel | carousel | story. post and reel share the same composer flow
        # (a video auto-routes to the reel composer); carousel adds multi-select; story
        # uses a distinct tail (no Next/caption screen, "Your story" button).
        self.post_type = (post_type or "post").lower()
        # Story entry method: False = create "+" then STORY tab; True = tap our own
        # bubble in the feed reels tray ("Add to story"). Both reach the same gallery.
        self.story_via_feed = bool(story_via_feed)
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
        stop_before_share: bool = False,
    ) -> dict:
        """Publie `media_paths` selon `post_type` (post/reel/carousel/story).

        `stop_before_share` runs the whole flow but stops on the last screen without tapping the
        share button, so the diagnostic bench can measure the navigation end to end without
        posting anything publicly. It is a flag on the production path on purpose: a bench that
        reimplements the flow to avoid the last tap would no longer be testing this workflow.

        Returns dict {success: bool, message: str, error_type: str | None}.
        """
        hashtags = hashtags or []
        media_paths = [p for p in (media_paths or []) if p]

        if not media_paths:
            return self._error("no_media", "At least one media path is required")
        for path in media_paths:
            if not os.path.isfile(path):
                return self._error("file_not_found", f"File not found: {path}")

        # 1. Push every media (MediaStore keeps the most recent at the top of the grid)
        if not self._push_all(media_paths):
            return self._error("push_failed", "Failed to push media to device")

        # 2. Launch Instagram + return to feed
        self._launch_and_home()

        # Story has a distinct tail (no Next/caption screen).
        if self.post_type == "story":
            return self._publish_story(stop_before_share)

        # 3. Open creation + ensure the gallery grid is visible
        err = self._open_creation_and_gallery()
        if err:
            return err

        # 4. Select media (carousel = multi-select N, else the first thumbnail)
        self._status("selecting", "Selecting media from gallery...")
        if self.post_type == "carousel":
            if not self._select_carousel(len(media_paths)):
                return self._error("gallery_item_not_found", "Could not select carousel media")
        else:
            if not self._tap(CC.first_gallery_item_xpath(), timeout=6):
                return self._error("gallery_item_not_found", "Could not select media from gallery")
            time.sleep(1.0)

        # 5. Compose (Next-loop -> caption) and share
        return self._compose_and_share(caption, hashtags, stop_before_share)

    # ------------------------------------------------------------------
    # Shared stages
    # ------------------------------------------------------------------

    def _push_all(self, media_paths: List[str]) -> bool:
        for path in media_paths:
            self._status("uploading", f"Pushing media: {os.path.basename(path)}")
            remote_path = push_media(self.device_id, path)
            if not remote_path:
                return False
            trigger_media_scan(self.device_id, remote_path, path, log=self._log)
            time.sleep(scan_wait_for(path))
        return True

    def _launch_and_home(self) -> None:
        self._status("navigating", "Opening Instagram...")
        self._launch_app()
        try:
            if not self._a["nav"].navigate_to_home():
                self._log("warning", "navigate_to_home returned False (continuing)")
        except Exception as e:
            self._log("warning", f"navigate_to_home raised (non-fatal): {e}")
        time.sleep(1.0)

    def _open_creation_and_gallery(self) -> Optional[dict]:
        """Open creation, dismiss the draft modal, select the destination tab for the
        publish type (POST/REEL/STORY) and ensure the gallery grid is visible.
        Returns an error dict on failure, else None."""
        self._status("navigating", "Opening creation...")
        if not self._tap(CC.create_button_flow_xpaths(), timeout=6):
            return self._error("create_not_found", "Create button not found")
        time.sleep(1.2)

        if self._tap(CC.draft_dismiss_xpaths(), timeout=2):
            self._log("info", "Dismissed draft modal (Start new video)")
            time.sleep(0.8)

        # Select the destination tab (the create camera opens on the last-used mode, e.g.
        # REEL; carousel multi-select only exists under POST). Non-fatal: if creation
        # opened straight on the gallery the tabs are absent.
        if self._tap(CC.destination_tab_xpaths(self.post_type), timeout=3):
            self._log("info", f"Selected destination tab for {self.post_type}")
            time.sleep(0.8)

        # Create can land on the camera instead of the gallery grid; open it if needed.
        self._ensure_gallery_open()
        return None

    def _select_carousel(self, count: int) -> bool:
        """Enable multi-select and select exactly the first `count` gallery thumbnails.

        Three device-confirmed gotchas (Cartography Lab):
          1. Enabling multi-select auto-selects the *previewed* thumbnail, which is NOT
             always grid #1 — a stale preview from a previous session can be selected at
             an arbitrary grid position. Relying on the grid index then mixes the wrong
             media into the carousel and makes the preview jump between files.
          2. Re-tapping a selected thumbnail DESELECTS it.
          3. Instagram numbers the carousel in TAP ORDER, not in grid order, and the grid
             is date-sorted DESCENDING — so grid #1 is the media pushed LAST. Tapping
             1, 2, 3 therefore published the slides backwards (device report 2026-07-26:
             slide-03, slide-02, slide-01). We walk the positions from `count` down to 1,
             which taps the oldest of the freshly pushed media first and restores the
             caller's order.
        So we first clear any auto/stale selection, then tap grid[count..1] on a clean
        slate. The grid is date-sorted descending, so positions 1..count are the freshest
        media (= the ones just pushed). Finally we verify the live selected count."""
        self._tap(CC.multi_select_xpaths(), timeout=4)
        time.sleep(0.6)

        self._clear_gallery_selection()
        # Reversed on purpose — see gotcha 3. `media_paths[0]` must be slide 1 of the carousel.
        for i in range(count, 0, -1):
            if self._tap(CC.gallery_item_xpath(i), timeout=4):
                time.sleep(0.4)
            else:
                self._log("warning", f"Carousel item {i} not found")

        final = self._selected_media_count()
        self._log("info", f"Carousel selection: {final}/{count} media selected")
        # A carousel needs >= 2 media; below that Instagram would publish a single post.
        return final >= 2

    def _clear_gallery_selection(self, max_taps: int = 12) -> None:
        """Deselect every currently-selected thumbnail (handles stale auto-selection).

        Tapping a selected thumbnail toggles it off; we repeat until none remain so the
        subsequent grid[1..N] taps start from a deterministic empty state."""
        for _ in range(max_taps):
            if self._selected_media_count() == 0:
                return
            if not self._tap(CC.selected_media_xpath(), timeout=2):
                return
            time.sleep(0.3)
        self._log("warning", "Could not fully clear gallery selection before carousel")

    def _selected_media_count(self) -> int:
        """Number of gallery thumbnails currently selected (content-desc based)."""
        try:
            return len(self.device.xpath(CC.selected_media_xpath()).all())
        except Exception as e:
            self._log("debug", f"selected media count failed: {e}")
            return 0

    def _compose_and_share(self, caption: str, hashtags: List[str], stop_before_share: bool = False) -> dict:
        # Next-loop to the caption composer
        self._status("navigating", "Navigating to caption screen...")
        if not self._advance_to_composer():
            return self._error("composer_not_reached", "Caption screen was not reached")

        # Caption + hashtags
        full_caption = self._build_caption(caption, hashtags)
        if full_caption:
            self._status("filling", "Entering caption...")
            if not self._fill_caption(full_caption):
                return self._error("caption_fill_failed", "Could not enter caption")
            time.sleep(0.5)

        # Rehearsal: the share button being on screen is the proof the flow reached the end.
        if stop_before_share:
            self._dismiss_keyboard()
            if not self._present(CC.share_button_xpaths(), timeout=6):
                return self._error("share_not_found", "Share button not found")
            self._status("success", f"{self.post_type} reached the share screen (not published)")
            self._log("info", f"Instagram {self.post_type}: stopped before sharing")
            return {"success": True, "message": f"{self.post_type} reached the share screen (not published)", "error_type": None}

        # Share (the IME may still cover the footer button: dismiss + retry once)
        self._status("publishing", "Publishing...")
        if not self._tap(CC.share_button_xpaths(), timeout=6):
            self._dismiss_keyboard()
            if not self._tap(CC.share_button_xpaths(), timeout=6):
                return self._error("share_not_found", "Share button not found")

        if not self._wait_for_publish_commit():
            return self._error(
                "publish_not_committed",
                "Instagram did not appear to finish publishing before timeout",
            )

        label = self.post_type
        self._status("success", f"{label} published successfully")
        self._log("info", f"Instagram {label} published")
        return {"success": True, "message": f"{label} published successfully", "error_type": None}

    def _publish_story(self, stop_before_share: bool = False) -> dict:
        """Story flow: enter (create '+' STORY tab OR feed tray) -> gallery -> select ->
        'Your story' -> dismiss the one-time story-to-story promo modal."""
        if self.story_via_feed:
            err = self._open_story_from_feed_tray()
        else:
            err = self._open_creation_and_gallery()
        if err:
            return err
        self._status("selecting", "Selecting media from gallery...")
        if not self._tap(CC.first_gallery_item_xpath(), timeout=6):
            return self._error("gallery_item_not_found", "Could not select media for story")
        time.sleep(1.0)
        if stop_before_share:
            if not self._present(CC.story_publish_xpaths(), timeout=6):
                return self._error("share_not_found", "'Your story' button not found")
            self._status("success", "story reached the share screen (not published)")
            self._log("info", "Instagram story: stopped before sharing")
            return {"success": True, "message": "story reached the share screen (not published)", "error_type": None}

        self._status("publishing", "Publishing story...")
        if not self._tap(CC.story_publish_xpaths(), timeout=6):
            return self._error("share_not_found", "'Your story' button not found")
        # One-time "Introducing story-to-story sharing" promo can appear after publish.
        if self._tap(CC.story_share_promo_dismiss_xpaths(), timeout=4):
            self._log("info", "Dismissed story-to-story sharing promo")
        if not self._wait_for_publish_commit():
            return self._error("publish_not_committed", "Story publish did not confirm before timeout")
        self._status("success", "Story published successfully")
        self._log("info", "Instagram story published")
        return {"success": True, "message": "story published successfully", "error_type": None}

    def _open_story_from_feed_tray(self) -> Optional[dict]:
        """2nd story entry: tap our own bubble in the feed reels tray, then ensure the
        gallery grid is visible. Returns an error dict on failure, else None."""
        self._status("navigating", "Opening story from feed tray...")
        if not self._tap(CC.feed_story_tray_add_xpaths(), timeout=6):
            return self._error("story_tray_not_found", "Feed 'Add to story' bubble not found")
        time.sleep(1.2)
        self._ensure_gallery_open()
        return None

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

    def _ensure_gallery_open(self) -> None:
        """If the create flow landed on the camera, open the gallery picker."""
        if self._a["click"]._is_element_present(CC.gallery_grid_xpaths()):
            return
        self._log("info", "Gallery grid not visible; opening gallery from camera")
        if self._tap(CC.gallery_open_xpaths(), timeout=3):
            self._a["click"]._wait_for_element(CC.gallery_grid_xpaths(), timeout=5, silent=True)

    def _fill_caption(self, text: str) -> bool:
        if not self._tap(CC.composer_xpaths(), timeout=5):
            self._log("warning", "Caption field not focusable")
            return False
        time.sleep(0.4)
        try:
            # clear_first: the composer can restore a previous draft caption; clearing
            # avoids appending a duplicate.
            typed = bool(self._a["kb"].type_text(text, clear_first=True, human_typing=True))
        except Exception as e:
            self._log("warning", f"type_text failed: {e}")
            return False
        # Tapping the caption opens a full-screen editor (custom auto-typing IME). The
        # footer Share button is hidden there; confirm with OK to return to the composer.
        # Back does NOT dismiss the custom IME, so OK is the reliable path.
        if not self._tap(CC.caption_confirm_xpaths(), timeout=4):
            self._dismiss_keyboard()
        time.sleep(0.6)
        return typed

    def _dismiss_keyboard(self) -> None:
        """Press back once to close the soft keyboard (fallback when OK is not found)."""
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

    def _present(self, selectors, timeout: float = 4.0) -> bool:
        """True if any selector is on screen, WITHOUT touching it.

        Used by the rehearsal mode: reaching the share button proves the whole navigation worked,
        and not tapping it is what keeps the run from publishing anything.
        """
        device = self._a["click"].device
        if isinstance(selectors, str):
            selectors = [selectors]
        deadline = time.time() + timeout
        while time.time() < deadline:
            for selector in selectors:
                try:
                    if device.xpath(selector).exists:
                        return True
                except Exception:
                    continue
            time.sleep(0.3)
        return False

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
