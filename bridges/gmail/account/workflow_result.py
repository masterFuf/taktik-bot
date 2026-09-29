"""Result emission helpers for Gmail account bridge workflows."""

from collections.abc import Callable


def finish_account_result(
    result: dict,
    *,
    workflow_type: str,
    email: str,
    send_status: Callable[[str, str], None],
    send_message: Callable[..., None],
    extra: dict | None = None,
) -> int:
    """Emit the historical account_result payload for Gmail account flows."""
    success = bool(result.get("success"))
    send_status("success" if success else "error", result.get("message", ""))
    payload = {
        "success": success,
        "workflow": workflow_type,
        "email": email,
        "message": result.get("message", ""),
        "error_type": result.get("error_type"),
    }
    if extra:
        payload.update(extra)
    send_message("account_result", **payload)
    return 0 if success else 1


__all__ = ["finish_account_result"]
