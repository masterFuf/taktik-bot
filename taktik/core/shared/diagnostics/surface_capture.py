"""One capture of one screen: the pixels, the tree, and a name for its shape.

The Lab's auto-test says an action stopped working. It never says what was on screen, and its
baseline is filed by (platform, language, device) — no version, nothing describing the screen. So
a regression arrives as an unexplained flip, and two different screens share one cell.

A capture answers the "what did it look like" half. `layout_fingerprint` answers the "was it the
same screen" half. Together they let a surface be followed over time, which is the only way to
name the failure that has no version number: Instagram serves story layout variants from its
servers, so a validated function can break while every version string stays put.

Read-only and best-effort by construction — a diagnostic that can end a run is worse than no
diagnostic, which is the rule `capture_screen_snapshot` was already written to.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger

from taktik.core.shared.app_paths import get_app_subdir
from taktik.core.shared.device.app_inspection import foreground_package
from taktik.core.shared.diagnostics.layout_fingerprint import (
    layout_fingerprint,
    screen_density,
    screen_skeleton,
)
from taktik.core.shared.diagnostics.screen_snapshot import capture_screen_snapshot


def captures_dir(platform: str, surface: str) -> str:
    """Where a surface's captures live — beside the Lab's baselines, not among run incidents."""
    safe = lambda value: ''.join(  # noqa: E731
        c if c.isalnum() or c in '-_' else '-' for c in (value or 'unknown')
    ).lower()[:40]
    base = get_app_subdir('debug_ui', 'cartography', '_captures', create=False) or os.path.join(
        os.path.expanduser('~'), 'taktik-desktop', 'debug_ui', 'cartography', '_captures')
    return os.path.join(base, safe(platform), safe(surface))


def capture_surface(
    device: Any,
    *,
    platform: str,
    surface: str,
    app_version: str = '',
    language: str = '',
    device_model: str = '',
    action_outcome: Optional[str] = None,
    run_id: Optional[str] = None,
    force_files: bool = False,
) -> Optional[Dict[str, Any]]:
    """Fingerprint the current screen, and keep its files when they are worth keeping.

    The fingerprint, the skeleton and the counts are computed on every call — they are bytes, and
    the value is in the SERIES. The XML and the PNG are written only when the shape differs from
    this surface's last capture, or when `force_files` says the caller has a reason (an action
    that just failed is the reason that matters: that is the screen nobody can reconstruct later).

    Returns the capture record, or None if the screen could not be read at all.
    """
    try:
        hierarchy = device.dump_hierarchy()
    except Exception as exc:  # noqa: BLE001 — a diagnostic must never end a run
        logger.debug(f"[capture] hierarchy unavailable for {platform}/{surface}: {exc}")
        return None

    if not hierarchy:
        return None

    fingerprint = layout_fingerprint(hierarchy)
    record: Dict[str, Any] = {
        'captureId': datetime.now().strftime('%Y-%m-%d-%H-%M-%S'),
        'platform': platform,
        'surface': surface,
        'appVersion': app_version,
        'language': language,
        'deviceModel': device_model,
        'layoutFingerprint': fingerprint,
        'skeleton': screen_skeleton(hierarchy) or [],
        'density': screen_density(hierarchy),
        'runId': run_id,
        'actionOutcome': action_outcome,
        # WHICH APP took this screenshot. Without it a capture taken in Chrome -- because a tap
        # landed on a sponsored link and left the app -- is indistinguishable from one taken in
        # Instagram, and the archive says only "a screen the catalogue could not name".
        #
        # Measured on a Pixel: `app_current()` costs ~440 ms, about TWICE a `dump_hierarchy`
        # (~225 ms). It is paid here anyway because this function is only reached on a failure
        # that already burned its timeout, and `miss_capture` caps it at six per run. Reading the
        # package out of the XML we already hold would be free but WRONG: the first `package=`
        # attribute in a dump is the system UI's status bar, not the app on screen.
        'foregroundPackage': foreground_package(device),
        # `dump_hierarchy` goes through AOSP's `stripInvalidXMLChars`, which eats emoji. Said in
        # the record so nobody spends an afternoon wondering why an archived handle does not
        # match the one on screen.
        'lossy': ['emoji-stripped-by-aosp'],
        'xmlPath': None,
        'screenshotPath': None,
    }

    directory = captures_dir(platform, surface)
    previous = _last_record(directory)
    changed = previous is None or previous.get('layoutFingerprint') != fingerprint
    record['layoutChanged'] = bool(changed)

    if changed or force_files:
        base = capture_screen_snapshot(
            device,
            label=f"{surface}_{(fingerprint or 'unreadable')[-8:]}",
            with_image=True,
            directory=directory,
        )
        if base:
            record['xmlPath'] = f"{base}.xml"
            record['screenshotPath'] = f"{base}.png"

    _append_record(directory, record)
    return record


def _index_path(directory: str) -> str:
    return os.path.join(directory, 'captures.jsonl')


def _last_record(directory: str) -> Optional[Dict[str, Any]]:
    """The most recent capture of this surface, or None. Never raises."""
    try:
        path = _index_path(directory)
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as handle:
            last = None
            for line in handle:
                line = line.strip()
                if line:
                    last = line
        return json.loads(last) if last else None
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"[capture] could not read the index in {directory}: {exc}")
        return None


def _append_record(directory: str, record: Dict[str, Any]) -> None:
    """One line per capture. Append-only: the series IS the artefact."""
    try:
        os.makedirs(directory, exist_ok=True)
        with open(_index_path(directory), 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"[capture] could not append to the index in {directory}: {exc}")


__all__ = ['capture_surface', 'captures_dir']
