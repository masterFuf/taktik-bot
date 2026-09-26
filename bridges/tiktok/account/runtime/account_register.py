"""TikTok account registration adapter (the run is the core's `run_tiktok_account`)."""

from bridges.tiktok.runtime.ipc import send_error, send_log, send_message, send_status
from taktik.core.social_media.tiktok.workflows.management.agent_handler import (
    TIKTOK_ACCOUNT_REGISTER_WORKFLOW_ID,
)


class TikTokAccountRegisterMixin:
    """Run TikTok account registration from the bridge payload."""

    def _run_register(self, device) -> int:
        params = self._account_params(TIKTOK_ACCOUNT_REGISTER_WORKFLOW_ID)
        if params is None:
            return 1
        method = params["method"]

        send_status("running", f"Starting register ({method})...")
        send_log("info", f"Register workflow - method={method}")

        try:
            result = self._launch_account(device, TIKTOK_ACCOUNT_REGISTER_WORKFLOW_ID, params)
            outcome = "success" if result["success"] else "error"
            send_status(outcome, result.get("message", ""))
            send_message(
                "account_result",
                success=result["success"],
                workflow="register",
                step=result.get("step", "unknown"),
                message=result.get("message", ""),
                error_type=result.get("error_type"),
            )
            return 0 if result["success"] else 1
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"Register error: {exc}")
            send_log("error", traceback.format_exc())
            return 1


__all__ = ["TikTokAccountRegisterMixin"]
