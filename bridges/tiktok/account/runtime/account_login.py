"""TikTok account login adapter (the run is the core's `run_tiktok_account`)."""

from bridges.tiktok.runtime.ipc import send_error, send_log, send_message, send_status
from taktik.core.social_media.tiktok.workflows.management.agent_handler import (
    TIKTOK_ACCOUNT_LOGIN_WORKFLOW_ID,
)


class TikTokAccountLoginMixin:
    """Run TikTok account login from the bridge payload."""

    def _run_login(self, device) -> int:
        params = self._account_params(TIKTOK_ACCOUNT_LOGIN_WORKFLOW_ID)
        if params is None:
            return 1
        username = params["username"]

        send_status("running", f"Starting login for @{username}...")
        send_log("info", f"Login workflow - @{username}")

        try:
            result = self._launch_account(device, TIKTOK_ACCOUNT_LOGIN_WORKFLOW_ID, params)
            outcome = "success" if result["success"] else "error"
            send_status(outcome, result.get("message", ""))
            send_message(
                "account_result",
                success=result["success"],
                workflow="login",
                username=username,
                message=result.get("message", ""),
                error_type=result.get("error_type"),
            )
            return 0 if result["success"] else 1
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"Login error: {exc}")
            send_log("error", traceback.format_exc())
            return 1


__all__ = ["TikTokAccountLoginMixin"]
