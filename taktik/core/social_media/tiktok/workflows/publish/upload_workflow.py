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
from taktik.core.social_media.tiktok.services.runtime.app_control import (
    force_stop_app_package,
    launch_app_non_blocking,
)
from taktik.core.social_media.tiktok.services.runtime.package_resolver import resolve_tiktok_package
from taktik.core.social_media.tiktok.services.publish.dialogs import (
    dismiss_post_popups,
    handle_permission_dialog,
    handle_publish_confirmation_dialog,
)
from taktik.core.social_media.tiktok.services.publish.caption import (
    MAX_TIKTOK_HASHTAGS,
    build_caption,
    sanitize_caption_and_hashtags,
)
from taktik.core.social_media.tiktok.services.publish.commit import (
    PublishCommitCallbacks,
    wait_for_publish_commit,
)
from taktik.core.social_media.tiktok.services.publish.hashtag_suggestions import (
    tap_hashtag_suggestion_from_dump,
)
from taktik.core.social_media.tiktok.services.publish.navigation import (
    advance_to_post_screen,
    ensure_gallery_picker_open,
    select_first_gallery_item,
    tap_create_button,
    tap_upload_button,
)
from taktik.core.social_media.tiktok.services.publish.progress import get_publish_progress_percent
from taktik.core.social_media.tiktok.services.publish.screen_detector import (
    is_post_screen,
    is_video_edit_screen,
    wait_for_tiktok_home,
)
from taktik.core.social_media.tiktok.services.publish.text_input import (
    clear_caption_text,
    type_caption_text,
)
from taktik.core.social_media.tiktok.services.publish.touch_fallbacks import tap_caption_focus_fallback
from taktik.core.social_media.tiktok.ui.detectors.keyboard import dismiss_keyboard
from taktik.core.social_media.tiktok.ui.selectors.flows.publish import (
    PUBLISH_COMPOSER_SELECTORS,
    PUBLISH_EDITOR_SELECTORS,
    PUBLISH_PROGRESS_SELECTORS,
)
from taktik.core.social_media.tiktok.workflows.runtime.notifier import (
    LoggingWorkflowNotifier,
    create_workflow_notifier_context,
)
from taktik.core.social_media.tiktok.ui.xpath import find_element, tap_element


_NULL_NOTIFIER, _CURRENT_NOTIFIER, _ipc = create_workflow_notifier_context(
    "tiktok_publish_notifier",
    default=LoggingWorkflowNotifier(),
)

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

    def __init__(self, device, device_id: str, notifier=None):
        self.device = device
        self.device_id = device_id
        self._notifier = notifier or _NULL_NOTIFIER

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
        token = _CURRENT_NOTIFIER.set(self._notifier)
        try:
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
                force_stop_app_package(self.device_id, tiktok_pkg, log=_ipc.log)
                time.sleep(0.5)
                launch_app_non_blocking(self.device_id, tiktok_pkg, log=_ipc.log)
            # Wait for TikTok to fully load — 4s matches the automation bridge delay.
            # For very slow devices, also poll for the Create button before proceeding.
            time.sleep(4)
            wait_for_tiktok_home(self.device, timeout=30.0, log=_ipc.log)
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

            dismiss_post_popups(self.device, log=_ipc.log)

            # 6. Appuyer sur le bouton Create
            _ipc.status("navigating", "Tapping Create button...")
            if not tap_create_button(self.device, log=_ipc.log):
                return self._error("create_btn_not_found", "Create button not found")
            time.sleep(1.0)
            if handle_permission_dialog(self.device, self.device_id, log=_ipc.log):
                time.sleep(1.0)

            # 7. Taper le bouton Upload/Gallery dans le panneau de création caméra
            _ipc.status("navigating", "Tapping Upload/Gallery button...")
            if not tap_upload_button(self.device, log=_ipc.log):
                dismiss_post_popups(self.device, log=_ipc.log)
                if handle_permission_dialog(self.device, self.device_id, log=_ipc.log):
                    time.sleep(0.8)
                if not tap_upload_button(self.device, log=_ipc.log):
                    return self._error("upload_btn_not_found", "Upload button not found in creation panel")
            if not ensure_gallery_picker_open(self.device, self.device_id, log=_ipc.log):
                return self._error("gallery_not_opened", "TikTok gallery did not open after tapping Upload")

            # 8. Sélectionner le premier fichier de la galerie
            _ipc.status("selecting", "Selecting media from gallery...")
            if not select_first_gallery_item(self.device, log=_ipc.log):
                return self._error("gallery_item_not_found", "Could not select media from gallery")
            time.sleep(1.2)  # wait for TikTok to enable the Next button after item selection

            # 8. Taper "Next" jusqu'à l'écran de description (max 3 fois)
            _ipc.status("navigating", "Navigating to post screen...")
            if not advance_to_post_screen(self.device):
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
            if not tap_element(self.device, PUBLISH_COMPOSER_SELECTORS.post_btn, timeout=5.0):
                self._recover_from_video_edit_screen()
                if tap_element(self.device, PUBLISH_COMPOSER_SELECTORS.post_btn, timeout=3.0):
                    time.sleep(3.0)
                    dismiss_post_popups(self.device, log=_ipc.log)
                    _ipc.status("success", "Post published successfully!")
                    _ipc.log("info", "âœ… TikTok post published")
                    force_stop_app_package(self.device_id, tiktok_pkg, log=_ipc.log)
                    return {"success": True, "message": "Post published successfully", "error_type": None}
                return self._error("post_btn_not_found", "Post button not found")

            time.sleep(1.8)

            # TikTok can ask for an extra confirmation before the real publication.
            if handle_publish_confirmation_dialog(self.device, log=_ipc.log):
                time.sleep(1.2)

            # 11. Dismiss any system dialogs that may appear after posting
            # (e.g. Android "Add to Home Screen" / widget install prompt from TikTok)
            if not self._wait_for_publish_commit():
                return self._error(
                    "publish_not_committed",
                    "TikTok did not appear to finish publishing before timeout",
                )

            dismiss_post_popups(self.device, log=_ipc.log)

            # 12. Vérification succès (best-effort)
            _ipc.status("success", "Post published successfully!")
            _ipc.log("info", "✅ TikTok post published")

            # 13. Close TikTok after successful post
            force_stop_app_package(self.device_id, tiktok_pkg, log=_ipc.log)

            return {"success": True, "message": "Post published successfully", "error_type": None}
        finally:
            _CURRENT_NOTIFIER.reset(token)

    # ------------------------------------------------------------------
    # Publish stage helpers
    # ------------------------------------------------------------------

    def _wait_for_publish_commit(self, timeout: float = 120.0) -> bool:
        callbacks = PublishCommitCallbacks(
            handle_publish_confirmation=lambda: handle_publish_confirmation_dialog(self.device, log=_ipc.log),
            dismiss_popups=lambda: dismiss_post_popups(self.device, log=_ipc.log),
            get_progress_percent=lambda: get_publish_progress_percent(self.device, log=_ipc.log),
            is_on_post_screen=lambda: is_post_screen(self.device),
            has_success_indicator=lambda: find_element(
                self.device, PUBLISH_PROGRESS_SELECTORS.success_indicator, timeout=1.0
            ) is not None,
        )
        return wait_for_publish_commit(callbacks, timeout=timeout, log=_ipc.log)

    def _recover_from_video_edit_screen(self) -> bool:
        """Leave TikTok's video editor if a misplaced tap opened it."""
        if not is_video_edit_screen(self.device):
            return False

        _ipc.log("warning", "[publish] video editor opened; tapping cancel selector to return to post screen")
        if tap_element(self.device, PUBLISH_EDITOR_SELECTORS.video_edit_cancel_btn, timeout=2.0):
            time.sleep(1.2)
            return True
        return False

    # ------------------------------------------------------------------
    # Caption helpers
    # ------------------------------------------------------------------

    def _fill_caption(self, caption: str, hashtags: list[str]) -> bool:
        """Fill caption and validate TikTok hashtag suggestions one by one."""
        # ── Focus the EditText ───────────────────────────────────────────────
        el = find_element(self.device, PUBLISH_COMPOSER_SELECTORS.caption_input, timeout=5.0)
        try:
            if el:
                el.click()
            else:
                tap_caption_focus_fallback(self.device, log=_ipc.log)
            time.sleep(0.5)
        except Exception as e:
            _ipc.log("warning", f"[caption] focus failed: {e}")

        if not clear_caption_text(self.device_id, log=_ipc.log):
            _ipc.log("debug", "[caption] clear text skipped or failed")

        caption = (caption or "").strip()
        if caption and not type_caption_text(
            self.device_id, caption, delay_mean=85, delay_deviation=25, log=_ipc.log
        ):
            return False

        for index, tag in enumerate(hashtags or []):
            clean_tag = str(tag).lstrip("#").strip()
            if not clean_tag:
                continue

            prefix = " " if (index > 0 or caption) else ""
            token = f"{prefix}#{clean_tag}"
            if not type_caption_text(
                self.device_id, token, delay_mean=70, delay_deviation=18, log=_ipc.log
            ):
                return False

            time.sleep(0.25)
            if not self._confirm_hashtag_suggestion(clean_tag):
                _ipc.log("warning", f"[hashtag] could not confirm suggestion for #{clean_tag}")
                type_caption_text(self.device_id, " ", delay_mean=40, delay_deviation=10, log=_ipc.log)
                time.sleep(0.15)

        dismiss_keyboard(self.device, self.device_id, log=_ipc.log)
        return True

    def _confirm_hashtag_suggestion(self, expected_tag: str | None = None) -> bool:
        """Tap the first item in TikTok's hashtag autocomplete suggestion list.

        After typing a `#word`, TikTok shows a suggestion dropdown above the keyboard.
        Without tapping a suggestion the dropdown stays open and blocks the Post button.

        Returns True if a suggestion was tapped, False if none was found.
        """
        if tap_hashtag_suggestion_from_dump(self.device, expected_tag, log=_ipc.log):
            return True

        tapped = tap_element(self.device, PUBLISH_COMPOSER_SELECTORS.hashtag_suggestion_rows, timeout=2.0)
        if tapped:
            _ipc.log("debug", "[hashtag] suggestion tapped ✅")
            time.sleep(0.3)
        return tapped

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _error(error_type: str, message: str) -> dict:
        _ipc.log("error", f"❌ {message}")
        return {"success": False, "message": message, "error_type": error_type}
