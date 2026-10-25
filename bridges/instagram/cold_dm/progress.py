"""Progress event emitters for the Instagram Cold DM bridge: the recipient processed, the text sent,
the text the DM rule refused."""

from __future__ import annotations

import json

from taktik.core.ai.dm_rules import AiDmRefusal


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


def emit_cold_dm_text_refused(*, current: int, username: str, message: str, refusal: AiDmRefusal) -> None:
    """A text the AI mode wrote for one recipient and the DM rule refused, nothing typed: for the
    app's journal of the DM texts, with the rule and its measure."""
    print(json.dumps({
        "type": "cold_dm_text_refused",
        "current": current,
        "username": username,
        "message": message,
        "textRefusal": refusal.as_line(),
    }), flush=True)
