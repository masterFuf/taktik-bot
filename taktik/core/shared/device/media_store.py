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

Pushed files are named the way the stock camera names its shots (`IMG_…`, `VID_…`), on every phone
and for every platform (no vendor scheme such as `PXL_`): a name that carries the tool's brand in
the camera folder is a signal. Since such a name no longer tells our
files from the user's, cleanup deletes only the exact paths recorded in `pushed_media_registry`.

References:
  - https://developer.android.com/reference/android/provider/MediaStore
  - https://stackoverflow.com/questions/5739140/mediastore-uri-to-load-image
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Callable, Iterable, Optional

from loguru import logger

from . import pushed_media_registry


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VIDEO_EXTS = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.3gp')

DEFAULT_REMOTE_DIR = '/sdcard/DCIM/Camera'
NORMALIZED_REMOTE_DIR = '/storage/emulated/0/DCIM/Camera'

# Stock camera naming: `IMG_yyyyMMdd_HHmmss` / `VID_yyyyMMdd_HHmmss`.
CAMERA_IMAGE_PREFIX = 'IMG'
CAMERA_VIDEO_PREFIX = 'VID'

# Prefixes of the files pushed before camera-style naming (YouTube used `YT`). Still swept, so
# phones lose them.
LEGACY_FILE_PREFIXES = ('TAKTIK', 'YT')

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


def camera_file_name(local_path: str, stamp: str, taken: Iterable[str] = ()) -> str:
    """The name the stock camera would give this medium, free among the names in `taken`.

    `IMG_<stamp>.jpg` for a picture, `VID_<stamp>.mp4` for a video (`stamp` = `yyyyMMdd_HHmmss`),
    then `_1`, `_2`… when that second is already used, as the AOSP camera does. Compared without
    case: the shared storage ignores it.
    """
    ext = os.path.splitext(local_path)[1].lower() or '.mp4'
    if ext == '.jpeg':
        ext = '.jpg'
    prefix = CAMERA_VIDEO_PREFIX if ext in VIDEO_EXTS else CAMERA_IMAGE_PREFIX
    used = {name.strip().lower() for name in taken}
    base = f'{prefix}_{stamp}'
    name, count = f'{base}{ext}', 0
    while name.lower() in used:
        count += 1
        name = f'{base}_{count}{ext}'
    return name


def _list_folder(device_id: str, remote_dir: str) -> Optional[list[str]]:
    """The names in `remote_dir`, or None when the device did not list it.

    Without the shell v2 protocol (Android < 7) `adb shell` exits 0 whatever the command did and
    its errors come on stdout, so an `ls:` error line is a failure too, not a file name.
    """
    code, out, err = _adb_shell(device_id, 'ls', '-1', remote_dir)
    names = [line.strip() for line in out.splitlines() if line.strip()]
    errors = [line.strip() for line in err.splitlines()]
    if code != 0 or any(line.startswith('ls:') for line in names + errors):
        return None
    return names


def _device_clock_stamp(device_id: str) -> str:
    """`yyyyMMdd_HHmmss` on the device's clock and time zone, which its camera uses."""
    _, out, _ = _adb_shell(device_id, 'date', '+%Y%m%d_%H%M%S')
    stamp = out.strip()
    if len(stamp) == 15 and stamp[8] == '_' and (stamp[:8] + stamp[9:]).isdigit():
        return stamp
    return time.strftime('%Y%m%d_%H%M%S')


def push_media(
    device_id: str,
    local_path: str,
    remote_dir: str = DEFAULT_REMOTE_DIR,
) -> Optional[str]:
    """Push a local media file to the device under a camera-style name, and record it.

    The name is picked free of every name already in the folder: `adb push` overwrites, and the
    file it would overwrite could be the user's. The exact path goes to `pushed_media_registry`,
    the only list `purge_pushed_media` deletes from.

    Parameters
    ----------
    device_id   : ADB serial of the target device
    local_path  : Local file path
    remote_dir  : Directory on device (default: /sdcard/DCIM/Camera)

    Returns the remote path on success, None on failure.
    """
    if not os.path.isfile(local_path):
        logger.error(f'[media_store] file not found: {local_path}')
        return None
    size = os.path.getsize(local_path)

    # mkdir -p the remote dir (no-op if exists)
    _adb_shell(device_id, 'mkdir', '-p', remote_dir)

    names = _list_folder(device_id, remote_dir)
    if names is None:
        logger.error(f'[media_store] cannot list {remote_dir}; not pushing without knowing what it would overwrite')
        return None

    filename = camera_file_name(local_path, _device_clock_stamp(device_id), names)
    remote_path = f'{remote_dir.rstrip("/")}/{filename}'

    if not _adb_push(device_id, local_path, remote_path):
        return None

    pushed_media_registry.record(device_id, remote_path, size)
    logger.info(f'[media_store] pushed {os.path.basename(local_path)} → {remote_path}')
    return remote_path


def parse_pushed_timestamp(filename: str, prefixes: Iterable[str] = LEGACY_FILE_PREFIXES) -> Optional[float]:
    """Epoch seconds encoded in a legacy `TAKTIK_` / `YT_` name, or None if the name is not one.

    Those names carry their own timestamp (`TAKTIK_20260726_011540.png`), so age is read from the
    name rather than from the device clock or the file mtime — both of which drift, and the mtime
    is deliberately rewritten by `trigger_media_scan` to sort the file to the top of Recents.
    """
    stem = os.path.splitext(filename)[0]
    for file_prefix in prefixes:
        prefix = f'{file_prefix}_'
        if not stem.startswith(prefix):
            continue
        try:
            return time.mktime(time.strptime(stem[len(prefix):], '%Y%m%d_%H%M%S'))
        except (ValueError, OverflowError):
            return None
    return None


def _delete_remote_media(device_id: str, remote_path: str) -> bool:
    """Remove the file and its MediaStore row. False when the file could not be removed."""
    rm_code, _, _ = _adb_shell(device_id, 'rm', '-f', remote_path)
    if rm_code != 0:
        return False

    # Drop the MediaStore row too: deleting the file alone leaves a ghost thumbnail in the
    # gallery, and the picker would offer a medium that no longer exists.
    normalized = remote_path.replace('/sdcard/', '/storage/emulated/0/')
    for uri in ('content://media/external/images/media', 'content://media/external/video/media'):
        _adb_shell(device_id, 'content', 'delete', '--uri', uri, '--where', f'_data=\'{normalized}\'')
    return True


def _still_holds_our_file(device_id: str, entry: dict) -> Optional[bool]:
    """True when the path still holds a file of the size we pushed, False when it is gone or
    holds another file, None when the device does not tell."""
    _, out, err = _adb_shell(device_id, 'stat', '-c', '%s', entry['path'])
    size = out.strip()
    if size.isdigit():
        return int(size) == entry['size']
    if 'No such file' in f'{out} {err}':
        return False
    return None


def _purge_registered(device_id: str, cutoff: float) -> int:
    forgotten = []
    removed = 0
    for entry in pushed_media_registry.load(device_id):
        if entry['pushed_at'] > cutoff:
            continue
        ours = _still_holds_our_file(device_id, entry)
        if ours is False:
            forgotten.append(entry['path'])  # gone, or another file under that name: never deleted
        elif ours and _delete_remote_media(device_id, entry['path']):
            forgotten.append(entry['path'])
            removed += 1
        # no answer from the device: kept, retried on the next run
    if forgotten:
        pushed_media_registry.forget(device_id, forgotten)
    return removed


def _purge_legacy_prefixed(device_id: str, remote_dir: str, cutoff: float) -> int:
    removed = 0
    for name in _list_folder(device_id, remote_dir) or ():
        pushed_at = parse_pushed_timestamp(name)
        if pushed_at is None or pushed_at > cutoff:
            continue
        if _delete_remote_media(device_id, f'{remote_dir.rstrip("/")}/{name}'):
            removed += 1
    return removed


def purge_pushed_media(
    device_id: str,
    remote_dir: str = DEFAULT_REMOTE_DIR,
    max_age_hours: float = 6.0,
    log: Optional[Callable[[str, str], None]] = None,
) -> int:
    """Delete media this bot pushed earlier, and forget them in MediaStore. Returns the count.

    Publishing copies a file into the device gallery and never removes it, so a phone automated
    for months accumulates every medium it ever posted until storage runs out.

    Deleting at the END of a publish would be the obvious place and is the wrong one: Instagram
    uploads in the background after the composer closes, so the file may still be read. This runs
    at the START of a run instead and only touches files older than `max_age_hours`, which cannot
    belong to a publish still in flight.

    What is ours comes from `pushed_media_registry`, the exact paths `push_media` wrote — never
    from a name, since the user's own shots are named the same way. A registered path is deleted
    only while it still holds a file of the size we pushed. Files from before the registry carry
    a legacy `TAKTIK_` or `YT_` prefix and a parsable timestamp; those are still swept in
    `remote_dir`.
    """
    def _log(level: str, msg: str):
        if log is not None:
            try:
                log(level, msg)
                return
            except Exception:
                pass
        getattr(logger, level if hasattr(logger, level) else 'debug')(msg)

    cutoff = time.time() - max_age_hours * 3600
    removed = _purge_registered(device_id, cutoff) + _purge_legacy_prefixed(device_id, remote_dir, cutoff)

    if removed:
        _log('info', f'[media_store] purged {removed} previously pushed media older than {max_age_hours:g}h')
    return removed


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
    log: Optional[Callable[[str, str], None]] = None,
    wait: bool = True,
) -> Optional[str]:
    """Convenience: push + scan + optional sleep. Returns remote path or None."""
    remote_path = push_media(device_id, local_path, remote_dir=remote_dir)
    if not remote_path:
        return None
    trigger_media_scan(device_id, remote_path, local_path, log=log)
    if wait:
        time.sleep(scan_wait_for(local_path))
    return remote_path
