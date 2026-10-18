"""Progress event emitters for the Instagram Cold DM bridge: the recipient processed, the text sent."""

from __future__ import annotations

import json


def emit_cold_dm_progress(*, current: int, total: int, username: str) -> None:
    print(json.dumps({
        "type": "progress",
        "current": current,
        "total": total,
        "username": username,
    }), flush=True)


def emit_cold_dm_sent(*, current: int, username: str, message: str, ai_written: bool) -> None:
    """The text the conversation took, for the app's journal of sent DMs."""
    print(json.dumps({
        "type": "cold_dm_sent",
        "current": current,
        "username": username,
        "message": message,
        "aiWritten": ai_written,
    }), flush=True)
