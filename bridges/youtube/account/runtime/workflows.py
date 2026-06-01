"""Workflow adapters for the YouTube account bridge."""

from bridges.youtube.base import _ipc, send_error, send_log, send_message, send_status
from taktik.core.social_media.youtube.workflows.account import YouTubeAccountWorkflow


def run_youtube_account_login(config: dict, *, device, device_id: str) -> int:
    """Run YouTube account login and emit the historical bridge result."""
    email = (config.get("email") or "").strip()
    if not email:
        send_error("email is required for YouTube login")
        return 1

    workflow = YouTubeAccountWorkflow(device, device_id, notifier=_ipc)
    result = workflow.login(
        email=email,
        password=(config.get("password") or ""),
    )
    return finish_youtube_account_result(result, workflow_type="login", email=email)


def run_youtube_account_logout(config: dict, *, device, device_id: str) -> int:
    """Run YouTube account logout and emit the historical bridge result."""
    email = (config.get("email") or "").strip()
    workflow = YouTubeAccountWorkflow(device, device_id, notifier=_ipc)
    result = workflow.logout(email=email)
    return finish_youtube_account_result(result, workflow_type="logout", email=email)


def finish_youtube_account_result(result: dict, *, workflow_type: str, email: str) -> int:
    """Emit the account_result event expected by Electron."""
    success = bool(result.get("success"))
    message = result.get("message", "")
    if success:
        send_status("success", message)
        send_message(
            "account_result",
            success=True,
            workflow=workflow_type,
            email=email,
            message=message,
        )
        return 0

    send_status("error", message)
    send_error(message or f"YouTube {workflow_type} failed")
    if result.get("error_type"):
        send_log("debug", f"YouTube {workflow_type} error_type={result['error_type']}")
    return 1


__all__ = ["run_youtube_account_login", "run_youtube_account_logout"]
