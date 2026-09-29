"""JSON stdout emitters for the Instagram notifications engagement bridge.

The run's own lines (`notification_step`, the command's `result`) are built by the core
(`workflows/notifications/commands.py`); the bridge prints them, and says in a `result` line
of its own why a command could not run.
"""

import json


def emit_notif_json(payload: dict, *, flush: bool = False) -> None:
    print(json.dumps(payload), flush=flush)


def emit_notif_error(error: str, *, flush: bool = False, **extra) -> None:
    """The command's last line when it could not run: a `result` that failed, and why."""
    emit_notif_json({"type": "result", "success": False, "error": error, **extra}, flush=flush)


__all__ = ["emit_notif_error", "emit_notif_json"]
