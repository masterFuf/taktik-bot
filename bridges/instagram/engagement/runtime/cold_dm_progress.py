"""Progress event emitters for the Instagram Cold DM bridge."""

from __future__ import annotations

import json


def emit_cold_dm_progress(*, current: int, total: int, username: str) -> None:
    print(json.dumps({
        "type": "progress",
        "current": current,
        "total": total,
        "username": username,
    }), flush=True)
