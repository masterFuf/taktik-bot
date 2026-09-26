"""Instagram account logout adapter (the run is the core's `run_instagram_account`)."""

from __future__ import annotations

from bridges.instagram.runtime.ipc import send_error, send_log, send_message, send_status
from taktik.core.social_media.instagram.workflows.management.agent_handler import (
    INSTAGRAM_ACCOUNT_LOGOUT_WORKFLOW_ID,
)


class AccountLogoutRunnerMixin:
    """Run Instagram logout and emit bridge JSON events."""

    def _run_logout(self, device) -> int:
        send_status("running", "Starting logout...")
        send_log("info", "Logout workflow")

        try:
            result = self._launch_account(device, INSTAGRAM_ACCOUNT_LOGOUT_WORKFLOW_ID, {})
            outcome = "success" if result["success"] else "error"
            send_status(outcome, result.get("message", ""))
            send_message(
                "account_result",
                success=result["success"],
                workflow="logout",
                message=result.get("message", ""),
                error_type=result.get("error_type"),
            )
            return 0 if result["success"] else 1
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"Logout error: {exc}")
            send_log("error", traceback.format_exc())
            return 1


__all__ = ["AccountLogoutRunnerMixin"]
