"""
Android MediaStore Helper (Shared)

Push a media file to the device and trigger MediaStore indexing so the file
appears at the top of the gallery on TikTok / Instagram / any picker.

Shared between Instagram and TikTok publish workflows.

Why a dedicated module?
-----------------------
MediaStore behaviour differs significantly across Android versions:

  - Android ≤ 9   (SDK < 29) → broadcast `MEDIA_SCANNER_SCAN_FILE` is sufficient
  - Android ≥ 10  (SDK ≥ 29) → broadcast still works for *videos* (preserves duration),
                                but for *images* the only reliable way to land at the
                                top of "Recents" is `content insert` with explicit
                                integer timestamps.
  - Path **must** be `/storage/emulated/0/...` (not `/sdcard/...` which is a symlink
    that the MediaStore on some kernels refuses to resolve).
  - The pushed file's mtime is preserved from the source — so we MUST `touch` it
    after pushing or it will be sorted to the bottom by `date_modified DESC`.
  - For images on SDK ≥ 29, the `content insert` bind values must use `:i:` (integer)
    not `:l:` (long) — `:l:` fails silently on some OEM kernels (Nokia / Realme).

References:
  - https://developer.android.com/reference/android/provider/MediaStore
  - https://stackoverflow.com/questions/5739140/mediastore-uri-to-load-image
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Callable, Optional

from loguru import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VIDEO_EXTS = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.3gp')

DEFAULT_REMOTE_DIR = '/sdcard/DCIM/Camera'
NORMALIZED_REMOTE_DIR = '/storage/emulated/0/DCIM/Camera'

DEFAULT_FILE_PREFIX = 'TAKTIK'

# How long to wait after scan (in seconds) for MediaStore to index the file
SCAN_WAIT_VIDEO = 5.0
SCAN_WAIT_IMAGE = 3.0


# ---------------------------------------------------------------------------
# Internal ADB helpers
# ---------------------------------------------------------------------------

def _adb_shell(device_id: str, *args: str, timeout: int = 15) -> tuple[int, str, str]:
    """Run `adb -s <device_id> shell <args>`. Returns (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ['adb', '-s', device_id, 'shell'] + list(args),
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, (result.stdout or '').strip(), (result.stderr or '').strip()
    except Exception as e:
        logger.debug(f'[media_store] adb shell error: {e}')
        return 1, '', str(e)


def _adb_push(device_id: str, local_path: str, remote_path: str, timeout: int = 60) -> bool:
    """Run `adb -s <device_id> push <local> <remote>`. Returns True on success."""
    try:
        result = subprocess.run(
            ['adb', '-s', device_id, 'push', local_path, remote_path],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            logger.error(f'[media_store] adb push failed: {result.stderr}')
            return False
        return True
    except Exception as e:
        logger.error(f'[media_store] adb push exception: {e}')
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_android_sdk_version(device_id: str) -> int:
    """Return the Android API level (e.g. 28 for Android 9, 30 for Android 11).

    Defaults to 28 (Android 9) on failure — the safe broadcast-only branch.
    """
    rc, out, _ = _adb_shell(device_id, 'getprop', 'ro.build.version.sdk')
    try:
        return int(out)
    except (TypeError, ValueError):
        logger.debug('[media_store] could not read SDK version, defaulting to 28')
        return 28


def is_video_file(path: str) -> bool:
    """True if the path's extension is a known video format."""
    return os.path.splitext(path)[1].lower() in VIDEO_EXTS


def guess_mime_type(path: str) -> str:
    """Guess the MIME type from extension. Defaults to image/jpeg or video/mp4."""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.png':
        return 'image/png'
    if ext == '.gif':
        return 'image/gif'
    if ext == '.mov':
        return 'video/quicktime'
    if ext in VIDEO_EXTS:
        return 'video/mp4'
    return 'image/jpeg'


def push_media(
    device_id: str,
    local_path: str,
    remote_dir: str = DEFAULT_REMOTE_DIR,
    file_prefix: str = DEFAULT_FILE_PREFIX,
) -> Optional[str]:
    """Push a local media file to the device with a unique timestamped filename.

    Parameters
    ----------
    device_id   : ADB serial of the target device
    local_path  : Local file path
    remote_dir  : Directory on device (default: /sdcard/DCIM/Camera)
    file_prefix : Filename prefix used to make the file recognisable (default: TAKTIK)

    Returns the remote path on success, None on failure.
    """
    if not os.path.isfile(local_path):
        logger.error(f'[media_store] file not found: {local_path}')
        return None

    ext = os.path.splitext(local_path)[1] or '.mp4'
    ts = time.strftime('%Y%m%d_%H%M%S')
    filename = f'{file_prefix}_{ts}{ext}'
    remote_path = f'{remote_dir.rstrip("/")}/{filename}'

    # mkdir -p the remote dir (no-op if exists)
    _adb_shell(device_id, 'mkdir', '-p', remote_dir)

    if not _adb_push(device_id, local_path, remote_path):
        return None

    logger.info(f'[media_store] pushed {os.path.basename(local_path)} → {remote_path}')
    return remote_path


def trigger_media_scan(
    device_id: str,
    remote_path: str,
    local_path: str,
    log: Optional[Callable[[str, str], None]] = None,
) -> None:
    """Force Android MediaStore to index the pushed file.

    Strategy (mirrors the production-tested logic):
      - Always `touch` the file first (ADB push preserves source mtime → would
        be sorted to bottom of Recents).
      - **Videos** → broadcast `MEDIA_SCANNER_SCAN_FILE` only. `content insert`
        does NOT extract video metadata (duration would be 0:00). On SDK≥29 we
        also fire `content call scan_file` belt-and-suspenders.
      - **Images on SDK ≥ 29** → `content insert` with `:i:` integer timestamps
        on the normalised `/storage/emulated/0/` path. Falls back to broadcast.
      - **Images on SDK < 29** → broadcast on the original `/sdcard/` path.

    Parameters
    ----------
    device_id   : ADB serial
    remote_path : Path on device (e.g. `/sdcard/DCIM/Camera/foo.jpg`)
    local_path  : Original local path (used to detect mime / video vs image)
    log         : Optional `(level, message)` callback for IPC-style logging.
                  If None, falls back to `logger.debug`.
    """
    def _log(level: str, msg: str):
        if log is not None:
            try:
                log(level, msg)
                return
            except Exception:
                pass
        getattr(logger, level if hasattr(logger, level) else 'debug')(msg)

    is_video = is_video_file(local_path)
    mime = guess_mime_type(local_path)
    normalized_path = remote_path.replace('/sdcard/', '/storage/emulated/0/')
    filename = os.path.basename(remote_path)
    sdk = get_android_sdk_version(device_id)

    try:
        # Step 0: update mtime so the file lands at top of Recents
        _adb_shell(device_id, 'touch', remote_path)
        _log('debug', f'[media_scan] touched {filename}')

        if is_video:
            # ── VIDEO: broadcast ONLY (preserves duration metadata) ──────────
            _log('debug', f'[media_scan] video → broadcast scan for {filename}')
            _adb_shell(
                device_id, 'am', 'broadcast',
                '-a', 'android.intent.action.MEDIA_SCANNER_SCAN_FILE',
                '-d', f'file://{normalized_path}'
            )
            if sdk >= 29:
                rc, _, _ = _adb_shell(
                    device_id, 'content', 'call',
                    '--uri', 'content://media',
                    '--method', 'scan_file',
                    '--arg', normalized_path
                )
                if rc == 0:
                    _log('debug', f'[media_scan] content call scan_file fired for {filename}')

        elif sdk >= 29:
            # ── IMAGE, Android 10+: content insert ───────────────────────────
            content_uri = 'content://media/external/images/media'
            now_sec = int(time.time())
            _log('debug', f'[media_scan] Android {sdk} → content insert for {filename}')
            try:
                result = subprocess.run(
                    ['adb', '-s', device_id, 'shell',
                     'content', 'insert',
                     '--uri', content_uri,
                     '--bind', f'_data:s:{normalized_path}',
                     '--bind', f'_display_name:s:{filename}',
                     '--bind', f'mime_type:s:{mime}',
                     '--bind', f'date_modified:i:{now_sec}',  # :i: integer required (not :l:)
                     '--bind', f'date_added:i:{now_sec}'],
                    capture_output=True, text=True, timeout=10
                )
                ok = result.returncode == 0 and 'Error' not in (result.stdout or '')
            except Exception as e:
                _log('debug', f'[media_scan] content insert exception: {e}')
                ok = False

            if not ok:
                _log('debug', f'[media_scan] insert failed → fallback broadcast for {filename}')
                _adb_shell(
                    device_id, 'am', 'broadcast',
                    '-a', 'android.intent.action.MEDIA_SCANNER_SCAN_FILE',
                    '-d', f'file://{normalized_path}'
                )
            else:
                _log('debug', f'[media_scan] content insert OK for {filename}')

        else:
            # ── IMAGE, Android ≤ 9: broadcast (original /sdcard/ path) ───────
            _log('debug', f'[media_scan] Android {sdk} → broadcast for {filename}')
            _adb_shell(
                device_id, 'am', 'broadcast',
                '-a', 'android.intent.action.MEDIA_SCANNER_SCAN_FILE',
                '-d', f'file://{remote_path}'
            )

        _log('info', f'📂 Media indexed in gallery: {filename}')

    except Exception as e:
        logger.warning(f'[media_store] scan error (non-fatal): {e}')


def scan_wait_for(local_path: str) -> float:
    """How long to wait after `trigger_media_scan` before opening the picker."""
    return SCAN_WAIT_VIDEO if is_video_file(local_path) else SCAN_WAIT_IMAGE


def push_and_scan(
    device_id: str,
    local_path: str,
    remote_dir: str = DEFAULT_REMOTE_DIR,
    file_prefix: str = DEFAULT_FILE_PREFIX,
    log: Optional[Callable[[str, str], None]] = None,
    wait: bool = True,
) -> Optional[str]:
    """Convenience: push + scan + optional sleep. Returns remote path or None."""
    remote_path = push_media(device_id, local_path, remote_dir=remote_dir, file_prefix=file_prefix)
    if not remote_path:
        return None
    trigger_media_scan(device_id, remote_path, local_path, log=log)
    if wait:
        time.sleep(scan_wait_for(local_path))
    return remote_path
