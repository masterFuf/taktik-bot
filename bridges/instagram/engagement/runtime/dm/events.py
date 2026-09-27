"""JSON stdout emitters for the Instagram DM bridge."""

import json


def emit_dm_json(payload: dict, *, flush: bool = False) -> None:
    print(json.dumps(payload), flush=flush)


def emit_dm_result(result: dict, *, flush: bool = False) -> None:
    """The bridge's last line: the command's result, or why it failed."""
    emit_dm_json({"type": "result", **result}, flush=flush)


def emit_dm_error(error: str, *, flush: bool = False) -> None:
    print(json.dumps({"type": "result", "success": False, "error": error}), flush=flush)


__all__ = ["emit_dm_error", "emit_dm_json", "emit_dm_result"]
