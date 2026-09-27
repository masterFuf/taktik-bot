"""
TikTok Upload Workflow
======================
Publish a video or an image on TikTok from a local file.

Flow :
  1. push the file to the device camera folder
  2. trigger the media scan so it appears in the gallery
  3. open the app and tap the create button
  4. tap the upload entry to open the gallery, rather than the camera
  5. select the first file, the most recent being the one just pushed
  6. tap the next button as many times as needed, taking off first the sound TikTok attached
     to the video on its own
  7. type the description, caption and hashtags
  8. Tape "Post" / "Publier"
  9. once TikTok confirmed the publication, delete from the camera folder the file pushed and the
     copy TikTok saved of the video (after a failure, both wait for the purge of a later publish)
"""

from __future__ import annotations

import os
import time

from taktik.core.shared.diagnostics.action_block import look_for_action_block
from taktik.core.shared.device.media_store import (
    delete_pushed_media,
    list_media_saved_by,
    purge_pushed_media,
    push_media,
    record_new_media_saved_by,
    trigger_media_scan,
    scan_wait_for,
)
from taktik.core.social_media.tiktok.services.runtime.app_control import (
    force_stop_app_package,
    restart_tiktok_package,
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
    POST_SCREEN_REACHED,
    SOUND_NOT_REMOVED,
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
    type_caption_checked,
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
from taktik.core.social_media.tiktok.ui.selectors.shell.navigation import NAVIGATION_SELECTORS


_NULL_NOTIFIER, _CURRENT_NOTIFIER, _ipc = create_workflow_notifier_context(
    "tiktok_publish_notifier",
    default=LoggingWorkflowNotifier(),
)

# ---------------------------------------------------------------------------
# Sélecteurs
# ---------------------------------------------------------------------------
# Every selector is centralized in
#   taktik/core/social_media/tiktok/ui/selectors/flows/publish/
# See that file for the resource-id history per app version.
#
# The Android permission popups are handled by the permission handler, which
# knows how to detect the Android version and the system language.
#

# ---------------------------------------------------------------------------
# Workflow class
# ---------------------------------------------------------------------------

class TikTokUploadWorkflow:
    """
    Publish a media file on TikTok.

    Parameters
    ----------
    device      : uiautomator2 device object
    device_id   : ADB serial (e.g. "emulator-5554")
    """

    def __init__(self, device, device_id: str, notifier=None, step_hook=None):
        self.device = device
        self.device_id = device_id
        self._notifier = notifier or _NULL_NOTIFIER
        # Optional injected callback (phase: str) -> None, called at each publish step so
        # the bridge can capture a screenshot + UI dump per step (Lab observability). The
        # core never touches the filesystem itself — no-op when not provided.
        self._step_hook = step_hook

    def _capture(self, phase: str) -> None:
        if self._step_hook:
            try:
                self._step_hook(phase)
            except Exception:
                pass

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
        Publish the given local file on TikTok.

        Returns
        -------
        dict with keys: success, message, error_type
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

            # 1. Check the file exists
            if not os.path.isfile(local_path):
                return self._error("file_not_found", f"File not found: {local_path}")

            # Reclaim what earlier runs pushed, as the Instagram post does: a phone that only
            # publishes here would otherwise keep every medium, legacy names included.
            try:
                purge_pushed_media(self.device_id, log=_ipc.log)
            except Exception as e:
                _ipc.log("warning", f"Media purge skipped: {e}")

            # What TikTok already saved in the camera folder, read before it can save its copy of
            # this video: the copy is what appears after, under TikTok's package.
            tiktok_pkg = package_name or resolve_tiktok_package(self.device_id)
            saved_before = list_media_saved_by(self.device_id, tiktok_pkg)
            if saved_before is None:
                _ipc.log("warning", "[gallery] the media TikTok saved could not be listed: "
                                    "its copy of this video will not be found")

            # 2-3. Push file + trigger MediaStore indexing (shared service)
            _ipc.log("info", f"📤 Pushing file to device: {os.path.basename(local_path)}")
            remote_path = push_media(self.device_id, local_path)
            if not remote_path:
                return self._error("push_failed", "Failed to push file to device")

            _ipc.log("info", "🔄 Triggering media scan...")
            trigger_media_scan(self.device_id, remote_path, local_path, log=_ipc.log)
            # Wait for MediaStore to index (videos take longer due to metadata extraction)
            time.sleep(scan_wait_for(local_path))

            published = False
            try:
                result = self._publish_from_gallery(caption, hashtags, tiktok_pkg)
                published = bool(result.get("success"))
                return result
            finally:
                self._release_gallery(tiktok_pkg, saved_before, remote_path, published)
        finally:
            _CURRENT_NOTIFIER.reset(token)

    # ------------------------------------------------------------------
    # Publish stage helpers
    # ------------------------------------------------------------------

    def _publish_from_gallery(self, caption: str, hashtags: list[str], tiktok_pkg: str) -> dict:
        """From a fresh start of TikTok to the confirmed publication of the medium just pushed."""
        # 4-5. Force-stop TikTok and relaunch — same pattern as automation workflows.
        # TikTokManager.restart() calls device.app_start(pkg, SplashActivity, stop=True),
        # which translates to `am start -S -n pkg/SplashActivity` (fast, non-blocking).
        # We replicate that here so publish and automation share the same boot path.
        _ipc.log("info", "🔄 Restarting TikTok (force stop + fresh launch)...")
        _ipc.status("navigating", "Restarting TikTok...")
        restart_tiktok_package(self.device, self.device_id, tiktok_pkg, log=_ipc.log)
        # Wait for TikTok to fully load — 4s matches the automation bridge delay.
        # For very slow devices, also poll for the Create button before proceeding.
        time.sleep(4)
        wait_for_tiktok_home(self.device, timeout=30.0, log=_ipc.log)
        _ipc.status("navigating", "TikTok ready")
        self._capture("01_home")

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

        # 6. Tap the create button
        _ipc.status("navigating", "Tapping Create button...")
        if not tap_create_button(self.device, log=_ipc.log):
            return self._error("create_btn_not_found", "Create button not found")
        time.sleep(1.0)
        if handle_permission_dialog(self.device, self.device_id, log=_ipc.log):
            time.sleep(1.0)
        self._capture("02_create")

        # 7. Tap the upload entry of the camera creation panel
        _ipc.status("navigating", "Tapping Upload/Gallery button...")
        if not tap_upload_button(self.device, log=_ipc.log):
            dismiss_post_popups(self.device, log=_ipc.log)
            if handle_permission_dialog(self.device, self.device_id, log=_ipc.log):
                time.sleep(0.8)
            if not tap_upload_button(self.device, log=_ipc.log):
                return self._error("upload_btn_not_found", "Upload button not found in creation panel")
        if not ensure_gallery_picker_open(self.device, self.device_id, log=_ipc.log):
            return self._error("gallery_not_opened", "TikTok gallery did not open after tapping Upload")
        self._capture("03_gallery")

        # 8. Select the first file of the gallery
        _ipc.status("selecting", "Selecting media from gallery...")
        if not select_first_gallery_item(self.device, log=_ipc.log):
            return self._error("gallery_item_not_found", "Could not select media from gallery")
        time.sleep(1.2)  # wait for TikTok to enable the Next button after item selection
        self._capture("04_media_selected")

        # 8. Tap Next up to the post screen, taking off the sound TikTok attached to the video
        _ipc.status("navigating", "Navigating to post screen...")
        reached = advance_to_post_screen(self.device, log=_ipc.log)
        if reached == SOUND_NOT_REMOVED:
            return self._error(
                "sound_not_removed",
                "The sound TikTok attached to the video could not be taken off: nothing was published",
            )
        if reached != POST_SCREEN_REACHED:
            return self._error("post_screen_not_reached", "TikTok post description screen was not reached")
        self._capture("05_post_screen")

        # 9. Type the description
        full_caption = build_caption(caption, hashtags)
        if full_caption:
            _ipc.status("filling", "Entering caption...")
            if not self._fill_caption(caption, hashtags):
                return self._error("caption_fill_failed", "Could not enter TikTok caption")
            time.sleep(0.5)
            self._capture("06_caption")

        # 10. Taper "Post"
        _ipc.status("publishing", "Publishing...")
        self._capture("07_before_post")
        self._recover_from_video_edit_screen()
        if not tap_element(self.device, PUBLISH_COMPOSER_SELECTORS.post_btn, timeout=5.0):
            self._recover_from_video_edit_screen()
            if tap_element(self.device, PUBLISH_COMPOSER_SELECTORS.post_btn, timeout=3.0):
                time.sleep(3.0)
                if self._refused():
                    return self._refused_error()
                dismiss_post_popups(self.device, log=_ipc.log)
                _ipc.status("success", "Post published successfully!")
                _ipc.log("info", "✅ TikTok post published")
                self._capture("08_posted")
                force_stop_app_package(self.device_id, tiktok_pkg, log=_ipc.log)
                return {"success": True, "message": "Post published successfully", "error_type": None}
            return self._error("post_btn_not_found", "Post button not found")

        time.sleep(1.8)
        # The one look after a write, before any popup is dismissed: a refusal is no timeout.
        if self._refused():
            return self._refused_error()

        # TikTok can ask for an extra confirmation before the real publication.
        if handle_publish_confirmation_dialog(self.device, log=_ipc.log):
            time.sleep(1.2)

        # 11. Dismiss any system dialogs that may appear after posting
        # (e.g. Android "Add to Home Screen" / widget install prompt from TikTok)
        committed = self._wait_for_publish_commit()
        if self._refused():
            return self._refused_error()
        if not committed:
            return self._error(
                "publish_not_committed",
                "TikTok did not appear to finish publishing before timeout",
            )

        dismiss_post_popups(self.device, log=_ipc.log)

        # 12. Vérification succès (best-effort)
        _ipc.status("success", "Post published successfully!")
        _ipc.log("info", "✅ TikTok post published")
        self._capture("08_posted")

        # 13. Close TikTok after successful post
        force_stop_app_package(self.device_id, tiktok_pkg, log=_ipc.log)

        return {"success": True, "message": "Post published successfully", "error_type": None}

    def _release_gallery(self, tiktok_pkg: str, saved_before, pushed_path: str, published: bool) -> None:
        """What this publication left in the camera folder: the video pushed, and the copy TikTok
        saved of it (a new file under TikTok's package in MediaStore). Both are recorded as media of
        this bot; deleted at once when TikTok confirmed the publication, and otherwise left to the
        purge of a later publish, which takes only what is several hours old (as for a pushed file)."""
        copies: list[str] = []
        if saved_before is not None:
            found = record_new_media_saved_by(self.device_id, tiktok_pkg, [row["path"] for row in saved_before])
            if found is None:
                _ipc.log("warning", "[gallery] TikTok's copy of this video could not be looked for: it stays in the gallery")
            else:
                copies = found
        if copies:
            _ipc.log("info", "[gallery] saved by TikTok during this publication: "
                             + ", ".join(os.path.basename(path) for path in copies))
        if not published:
            if copies:
                _ipc.log("info", f"[gallery] {len(copies)} copy(ies) saved by TikTok recorded; "
                                 "the purge of a later publish removes them with the video pushed")
            return
        if not copies:
            _ipc.log("info", "[gallery] TikTok saved no copy of this video in the camera folder")
        expected = 1 + len(copies)
        removed = delete_pushed_media(self.device_id, [pushed_path, *copies], log=_ipc.log)
        if removed == expected:
            _ipc.log("info", f"[gallery] camera folder as before the publication: video pushed "
                             f"and {len(copies)} copy(ies) saved by TikTok removed")
        else:
            _ipc.log("warning", f"[gallery] {removed} of {expected} file(s) of this publication removed; "
                                "the rest waits for the purge of a later publish")

    def _wait_for_publish_commit(self, timeout: float = 120.0) -> bool:
        callbacks = PublishCommitCallbacks(
            handle_publish_confirmation=lambda: handle_publish_confirmation_dialog(self.device, log=_ipc.log),
            dismiss_popups=lambda: dismiss_post_popups(self.device, log=_ipc.log),
            get_progress_percent=lambda: get_publish_progress_percent(self.device, log=_ipc.log),
            is_on_post_screen=lambda: is_post_screen(self.device),
            # "Published" signal: a success toast OR — far more reliable, since TikTok shows
            # no lasting success text — being back on a main feed screen (the bottom nav bar
            # reappears once we leave the composer). The loop only checks this AFTER we've left
            # the post screen, so the nav bar here means the publish committed and TikTok
            # redirected to the feed (verified on the 08_posted artifact). Lets the wait exit
            # immediately instead of falling through to the slow "stabilized" fallback.
            has_success_indicator=lambda: (
                find_element(self.device, PUBLISH_PROGRESS_SELECTORS.success_indicator, timeout=0.5) is not None
                or find_element(self.device, NAVIGATION_SELECTORS.bottom_nav_container, timeout=0.5) is not None
            ),
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
        # The field must hold exactly the caption before hashtags go after it.
        if caption and not type_caption_checked(
            self.device, self.device_id, caption, delay_mean=85, delay_deviation=25, log=_ipc.log
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

    def _refused(self) -> bool:
        """Is TikTok refusing the publication? The one look (production detector)."""
        from taktik.core.social_media.tiktok.actions.atomic.detection.detection_actions import (
            DetectionActions,
        )

        try:
            detector = DetectionActions(self.device)
        except Exception:  # noqa: BLE001 - no detector is not a refusal
            return False
        return look_for_action_block(detector, after="publish")

    def _refused_error(self) -> dict:
        return self._error("action_blocked", "TikTok refuses the publication (Too many requests)")

    def _error(self, error_type: str, message: str) -> dict:
        # Capture the failing screen — the most useful artifact to see WHERE it broke.
        self._capture(f"error_{error_type}")
        _ipc.log("error", f"❌ {message}")
        return {"success": False, "message": message, "error_type": error_type}
