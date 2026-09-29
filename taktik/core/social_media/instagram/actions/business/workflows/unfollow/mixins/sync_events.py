"""The stdout lines of the follow-graph sync: an account read, a list's progress.

One place for both lists, so the desktop reads the same line whichever list printed it
(`instagram_automation` in `taktik/core/contract` declares them).
"""

import json
from typing import Any, Dict

from loguru import logger


def emit_sync_user_discovered(list_type: str, username: str, display_name: str, is_new: bool) -> None:
    """One account read in a list."""
    try:
        print(json.dumps({
            "type": "sync_user_discovered",
            "list_type": list_type,
            "username": username,
            "display_name": display_name,
            "is_new": is_new,
        }), flush=True)
    except Exception as exc:
        logger.warning(f"sync_user_discovered not printed for @{username}: {exc}")


def emit_sync_progress(list_type: str, stats: Dict[str, Any]) -> None:
    """A list being read: its counters so far, and the count its tab shows (None without one).
    Printed when the read starts and after each screen that brought new names, so the page can
    say which list the run is reading before its first unfollow, and how far it got."""
    try:
        print(json.dumps({
            "type": "sync_progress",
            "list_type": list_type,
            "new_count": stats['new_count'],
            "updated_count": stats['updated_count'],
            "total_seen": stats['total_seen'],
            "expected": stats.get('expected'),
        }), flush=True)
    except Exception as exc:
        logger.warning(f"sync_progress not printed for the {list_type} list: {exc}")


__all__ = ["emit_sync_progress", "emit_sync_user_discovered"]
