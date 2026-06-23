"""JSON stdout emitters for the Instagram notifications engagement bridge."""

import json


def emit_notif_json(payload: dict, *, flush: bool = False) -> None:
    print(json.dumps(payload), flush=flush)


def emit_notif_error(error: str, *, flush: bool = False) -> None:
    emit_notif_json({"success": False, "error": error}, flush=flush)


def emit_notif_step(*, step: str, status: str, message: str = "", **extra) -> None:
    """Per-step live narration for the desktop Taktik Agent panel."""
    emit_notif_json(
        {"type": "notification_step", "step": step, "step_status": status,
         "message": message, **extra},
        flush=True,
    )


__all__ = ["emit_notif_json", "emit_notif_error", "emit_notif_step"]
