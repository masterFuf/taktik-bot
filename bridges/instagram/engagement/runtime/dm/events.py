"""JSON stdout emitters for the Instagram DM bridge."""

import json


def emit_dm_json(payload: dict, *, flush: bool = False) -> None:
    print(json.dumps(payload), flush=flush)


def emit_dm_error(error: str, *, flush: bool = False) -> None:
    emit_dm_json({"success": False, "error": error}, flush=flush)


__all__ = ["emit_dm_error", "emit_dm_json"]
