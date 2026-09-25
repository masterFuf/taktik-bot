"""Which files this bot pushed into a device's gallery, so cleaning up never has to guess.

Pushed media are named the way the stock camera names its own shots (`IMG_…`, `VID_…`), so a name
no longer tells our files from the user's. The cleanup therefore works from this list of exact
paths, written at push time, and never from a pattern: a path that is not in here is not ours.

One small JSON file per device in the data folder. Losing or corrupting it only means some of our
files stay on the phone; it can never make the cleanup delete anything else.
"""

from __future__ import annotations

import json
import os
import time
from typing import List, Optional

from loguru import logger

from taktik.core.shared.app_paths import get_app_subdir


REGISTRY_FOLDER = 'pushed_media'


def _registry_file(device_id: str) -> Optional[str]:
    folder = get_app_subdir(REGISTRY_FOLDER)
    if not folder:
        return None
    # Network serials carry a colon (`host:5555`), which Windows refuses in a file name.
    safe = ''.join(c if c.isalnum() or c in '._-' else '_' for c in device_id) or 'device'
    return os.path.join(folder, f'{safe}.json')


def _is_entry(entry) -> bool:
    return (
        isinstance(entry, dict)
        and isinstance(entry.get('path'), str)
        and bool(entry['path'])
        and type(entry.get('size')) is int
        and isinstance(entry.get('pushed_at'), (int, float))
    )


def load(device_id: str) -> List[dict]:
    """Recorded pushes for this device (`path`, `size`, `pushed_at`), oldest first."""
    path = _registry_file(device_id)
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        logger.warning(f'[media_registry] unreadable registry ignored: {e}')
        return []
    entries = data.get('pushed') if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if _is_entry(entry)]


def save(device_id: str, entries: List[dict]) -> bool:
    """Replace the device's list. Written aside then swapped in, so a crash never truncates it."""
    path = _registry_file(device_id)
    if not path:
        return False
    tmp = f'{path}.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'pushed': entries}, f, indent=2)
        os.replace(tmp, path)
        return True
    except OSError as e:
        logger.warning(f'[media_registry] could not write registry: {e}')
        return False


def record(device_id: str, remote_path: str, size: int, pushed_at: Optional[float] = None) -> bool:
    """Add one pushed file. Never raises: a missed record leaves a file behind, nothing worse."""
    try:
        entries = [entry for entry in load(device_id) if entry['path'] != remote_path]
        entries.append({
            'path': remote_path,
            'size': int(size),
            'pushed_at': time.time() if pushed_at is None else float(pushed_at),
        })
        return save(device_id, entries)
    except Exception as e:
        logger.warning(f'[media_registry] push not recorded: {e}')
        return False
