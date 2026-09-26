"""TikTok app-language change adapter (the run is the core's `run_tiktok_account`).

Mirrors the logout adapter exactly: the bridge layer converts a payload into a launcher call and
an `account_result` message, and owns none of the UI logic.
"""

from bridges.tiktok.runtime.ipc import send_error, send_log, send_message, send_status
from taktik.core.social_media.tiktok.workflows.management.agent_handler import (
    TIKTOK_ACCOUNT_CHANGE_LANGUAGE_WORKFLOW_ID,
)


class TikTokAccountLanguageMixin:
    """Run the TikTok app-language change from the bridge payload."""

    def _run_change_language(self, device) -> int:
        params = self._account_params(TIKTOK_ACCOUNT_CHANGE_LANGUAGE_WORKFLOW_ID)
        if params is None:
            return 1
        target = params["target_language"]

        send_status("running", f"Switching the app language to {target}...")
        send_log("info", f"Change language workflow -> {target}")

        try:
            result = self._launch_account(device, TIKTOK_ACCOUNT_CHANGE_LANGUAGE_WORKFLOW_ID, params)
            outcome = "success" if result["success"] else "error"
            send_status(outcome, result.get("error") or f"language: {result.get('language_after')}")
            send_message(
                "account_result",
                success=result["success"],
                workflow="change_language",
                message=result.get("error") or "",
                error_type=result.get("error_type"),
                # Both languages travel: "changed" and "was already there" are different facts,
                # and a caller that only sees success cannot tell them apart.
                language_before=result.get("language_before"),
                language_after=result.get("language_after"),
                already_set=result.get("already_set", False),
            )
            return 0 if result["success"] else 1
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"Change language error: {exc}")
            send_log("error", traceback.format_exc())
            return 1


__all__ = ["TikTokAccountLanguageMixin"]
