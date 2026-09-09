#!/usr/bin/env python3
"""Upload the next Central Clip Hubs video through the shared TikTok uploader."""

import hashlib
import re
import time
from pathlib import Path

import upload_next_tiktok as uploader

TARGET_ACCOUNT = "central.clips.hub"
VIDEO_DIR = Path("/home/tospak/Downloads/central.clip.hub")
POSTED_FILE = VIDEO_DIR / ".tiktok_posted_central.clips.hub.txt"
LOCK_FILE = VIDEO_DIR / ".tiktok_upload.lock"

FIXED_HASHTAGS = [
    "cartoon",
    "animation",
    "clips",
    "centralclipshub",
]


def make_caption(video: Path) -> tuple[str, list[str]]:
    """Build a neutral clip caption and remove a trailing downloader video ID."""
    title = re.sub(r"\s*\[[^\[\]]+\]\s*$", "", video.stem)
    caption = uploader.clean(title)
    return caption, FIXED_HASHTAGS.copy()


def file_sha256(path: Path) -> str:
    """Hash a local video without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def remote_copy_matches(device: str, local_path: Path, remote_path: str) -> bool:
    """Prove that the device copy is byte-for-byte the queued local video."""
    result = uploader.run(
        ["adb", "-s", device, "shell", "sha256sum", remote_path],
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        return False
    match = re.match(r"^([0-9a-fA-F]{64})(?:\s|$)", result.stdout or "")
    return bool(match and match.group(1).lower() == file_sha256(local_path))


def find_exact_media_uri(device: str, remote_path: str) -> str | None:
    """Return the single MediaStore URI for ``remote_path``, or fail closed."""
    normalized_path = remote_path.replace("/sdcard/", "/storage/emulated/0/")
    result = uploader.run(
        [
            "adb",
            "-s",
            device,
            "shell",
            "content",
            "query",
            "--uri",
            "content://media/external/video/media",
            "--projection",
            "_id:_display_name",
            "--where",
            f"_data='{normalized_path}'",
        ],
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        return None

    row_ids = re.findall(r"(?:^|\s)_id=(\d+)(?:,|\s|$)", result.stdout or "")
    if len(row_ids) != 1:
        return None
    return f"content://media/external/video/media/{row_ids[0]}"


def open_exact_media(device: str, package_name: str, content_uri: str) -> bool:
    """Open one exact MediaStore video in TikTok via an Android share intent."""
    stopped = uploader.run(
        ["adb", "-s", device, "shell", "am", "force-stop", package_name],
        capture_output=True,
        timeout=15,
    )
    if stopped.returncode != 0:
        return False

    started = uploader.run(
        [
            "adb",
            "-s",
            device,
            "shell",
            "am",
            "start",
            "-a",
            "android.intent.action.SEND",
            "-t",
            "video/mp4",
            "--eu",
            "android.intent.extra.STREAM",
            content_uri,
            "-p",
            package_name,
            "--grant-read-uri-permission",
        ],
        capture_output=True,
        timeout=30,
    )
    output = f"{started.stdout or ''}\n{started.stderr or ''}"
    return started.returncode == 0 and "Error:" not in output


def _wait_until(predicate, timeout: float, interval: float = 0.75) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _stop_package(device: str, package_name: str) -> None:
    try:
        uploader.run(
            ["adb", "-s", device, "shell", "am", "force-stop", package_name],
            capture_output=True,
            timeout=15,
        )
    except Exception:
        pass


def upload_exact(device: str, video: Path, caption: str, hashtags: list[str]) -> bool:
    """Publish the selected file by URI so TikTok cannot choose a stale thumbnail."""
    import uiautomator2 as u2

    from taktik.core.compat.selectors.setup import apply_version_overrides
    from taktik.core.shared.device.app_inspection import get_installed_app_version
    from taktik.core.shared.device.media_store import (
        delete_pushed_media,
        purge_pushed_media,
        push_media,
        trigger_media_scan,
    )
    from taktik.core.social_media.tiktok.services.publish.caption import (
        sanitize_caption_and_hashtags,
    )
    from taktik.core.social_media.tiktok.services.publish.dialogs import (
        handle_publish_confirmation_dialog,
    )
    from taktik.core.social_media.tiktok.services.publish.navigation import (
        advance_to_post_screen,
    )
    from taktik.core.social_media.tiktok.services.publish.screen_detector import (
        is_post_screen,
        is_video_edit_screen,
    )
    from taktik.core.social_media.tiktok.services.runtime.package_resolver import (
        resolve_tiktok_package,
    )
    from taktik.core.social_media.tiktok.ui.selectors.flows.publish import (
        PUBLISH_COMPOSER_SELECTORS,
    )
    from taktik.core.social_media.tiktok.ui.xpath import tap_element
    from taktik.core.social_media.tiktok.workflows.publish.upload_workflow import (
        TikTokUploadWorkflow,
    )

    remote_path = None
    package_name = None
    post_started = False
    publish_confirmed = False
    try:
        purge_pushed_media(device)
        remote_path = push_media(device, str(video))
        if not remote_path:
            print("Upload failed at stage: push_media")
            return False
        if not remote_copy_matches(device, video, remote_path):
            print("Upload failed at stage: device_copy_verification")
            return False

        trigger_media_scan(device, remote_path, str(video))
        content_uri = None

        def media_is_indexed() -> bool:
            nonlocal content_uri
            content_uri = find_exact_media_uri(device, remote_path)
            return content_uri is not None

        if not _wait_until(media_is_indexed, timeout=20.0):
            print("Upload failed at stage: media_store_lookup")
            return False

        package_name = resolve_tiktok_package(device)
        version = get_installed_app_version(device, package_name, "tiktok")
        if version:
            apply_version_overrides("tiktok", version)

        phone = u2.connect(device)
        if not open_exact_media(device, package_name, content_uri):
            print("Upload failed at stage: exact_media_open")
            return False

        composer_ready = _wait_until(
            lambda: is_video_edit_screen(phone) or is_post_screen(phone),
            timeout=30.0,
        )
        if not composer_ready:
            print("Upload failed at stage: editor_timeout")
            return False
        if not is_post_screen(phone) and not advance_to_post_screen(phone):
            print("Upload failed at stage: post_screen_navigation")
            return False

        caption, hashtags, dropped = sanitize_caption_and_hashtags(caption, hashtags)
        if dropped:
            print(f"Removed {dropped} hashtag(s) to satisfy TikTok limits.")
        workflow = TikTokUploadWorkflow(phone, device)
        if not workflow._fill_caption(caption, hashtags):
            print("Upload failed at stage: caption_verification")
            return False

        posted = tap_element(phone, PUBLISH_COMPOSER_SELECTORS.post_btn, timeout=5.0)
        if not posted:
            # TikTok 46.7.3 can leave its keyboard covering the visible Post button.
            if not is_post_screen(phone):
                print("Upload failed at stage: post_screen_recheck")
                return False
            phone.press("back")
            if not _wait_until(
                lambda: is_post_screen(phone), timeout=5.0, interval=0.25
            ):
                print("Upload failed at stage: keyboard_recovery")
                return False
            posted = tap_element(
                phone, PUBLISH_COMPOSER_SELECTORS.post_btn, timeout=5.0
            )
        if not posted:
            print("Upload failed at stage: post_button")
            return False

        post_started = True
        handle_publish_confirmation_dialog(phone)
        if not workflow._wait_for_publish_commit(timeout=120.0):
            print("Upload failed at stage: publish_confirmation")
            return False

        publish_confirmed = True
        return True
    except Exception as exc:
        print(f"Upload failed at stage: unexpected_error ({type(exc).__name__}: {exc})")
        return False
    finally:
        safe_to_clean = not post_started or publish_confirmed
        if package_name and safe_to_clean:
            _stop_package(device, package_name)
        if remote_path and safe_to_clean:
            try:
                delete_pushed_media(device, remote_path)
            except Exception as exc:
                print(f"Temporary media cleanup failed: {type(exc).__name__}: {exc}")


def main() -> int:
    """Apply this account's settings and run the existing safe upload workflow."""
    uploader.TARGET_ACCOUNT = TARGET_ACCOUNT
    uploader.VIDEO_DIR = VIDEO_DIR
    uploader.POSTED_FILE = POSTED_FILE
    uploader.LOCK_FILE = LOCK_FILE
    uploader.FIXED_HASHTAGS = FIXED_HASHTAGS
    uploader.make_caption = make_caption
    uploader.upload = upload_exact
    return uploader.main()


if __name__ == "__main__":
    raise SystemExit(main())
