"""What the phone was showing when something went wrong.

A run that ends on `navigation_lost` says so in its log and nothing else: the screen the bot could
not read is gone the moment the app is closed. Five such runs in one day, and the only honest
answer to "why" was a shrug — slow network, an Instagram interstitial, a screen nobody wrote a
selector for? The log cannot say, because nobody kept the screen.

This keeps it: the UI hierarchy (which is what the selectors read, so it answers the question
directly) and a screenshot beside it. Best effort by design — a diagnostic that can break a run
is worse than no diagnostic.

Files land in `%APPDATA%/taktik-desktop/logs/screens/`, next to the run logs the desktop already
writes, so a bad run and its screen are found together.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

from loguru import logger


def _snapshot_dir() -> str:
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    return os.path.join(appdata, 'taktik-desktop', 'logs', 'screens')


def capture_screen_snapshot(device: Any, label: str, *, with_image: bool = True) -> Optional[str]:
    """Save what is on screen right now. Returns the base path, or None.

    `label` names the moment (`navigation_lost`, `list_unavailable`…) — it becomes part of the
    file name, so a folder listing reads as a list of incidents.
    """
    if device is None:
        return None
    stamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    safe_label = ''.join(c if c.isalnum() or c in '-_' else '_' for c in (label or 'snapshot'))[:60]
    try:
        directory = _snapshot_dir()
        os.makedirs(directory, exist_ok=True)
        base = os.path.join(directory, f'{stamp}_{safe_label}')
    except Exception as exc:  # noqa: BLE001 — a diagnostic must never end a run
        logger.debug(f"Screen snapshot directory unavailable: {exc}")
        return None

    wrote = False

    # The hierarchy first: it is what the selectors read, so it answers "why did the selector miss"
    # directly, and it survives being read months later in a text editor.
    try:
        hierarchy = device.dump_hierarchy()
        if hierarchy:
            with open(f'{base}.xml', 'w', encoding='utf-8') as handle:
                handle.write(hierarchy)
            wrote = True
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Could not dump the hierarchy for {label}: {exc}")

    if with_image:
        try:
            image = device.screenshot()
            if image is not None:
                image.save(f'{base}.png', format='PNG')
                wrote = True
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Could not screenshot for {label}: {exc}")

    if wrote:
        logger.info(f"📸 Screen kept for diagnosis: {base}.* ({label})")
        return base
    return None
