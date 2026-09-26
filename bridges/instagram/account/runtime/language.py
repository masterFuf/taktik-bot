"""Instagram account change-language adapter (the run is the core's `run_instagram_account`).

Bridge runner mixin for the ``change_language`` workflowType. Reads the target
language code off the config, runs it through the launcher, and emits bridge JSON
events — including per-step ``change_language_step`` events used by the desktop
Agent panel for live narration. The core workflow stays stdout-free: this runner
injects a notifier callback that maps step callbacks to ``send_message``.
"""

from __future__ import annotations

from bridges.instagram.runtime.ipc import send_error, send_log, send_message, send_status
from taktik.core.social_media.instagram.workflows.management.agent_handler import (
    INSTAGRAM_ACCOUNT_CHANGE_LANGUAGE_WORKFLOW_ID,
)


class AccountChangeLanguageRunnerMixin:
    """Run the Instagram app-language change and emit bridge JSON events."""

    def _run_change_language(self, device) -> int:
        params = self._account_params(INSTAGRAM_ACCOUNT_CHANGE_LANGUAGE_WORKFLOW_ID)
        if params is None:
            return 1
        language = params["language"]

        send_status("running", f"Changing app language to {language}...")
        send_log("info", f"Change language workflow - {language}")

        def _emit_step(*, step: str, status: str, message: str = "", **extra) -> None:
            send_message(
                "change_language_step",
                step=step,
                step_status=status,
                message=message,
                **extra,
            )

        try:
            result = self._launch_account(
                device, INSTAGRAM_ACCOUNT_CHANGE_LANGUAGE_WORKFLOW_ID, params, notifier=_emit_step,
            )

            outcome = "success" if result["success"] else "error"
            send_status(outcome, result.get("message", ""))
            send_message(
                "account_result",
                success=result["success"],
                workflow="change_language",
                language=language,
                native_name=result.get("native_name"),
                message=result.get("message", ""),
                error_type=result.get("error_type"),
                app_restarted=result.get("app_restarted", False),
            )
            return 0 if result["success"] else 1
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"Change language error: {exc}")
            send_log("error", traceback.format_exc())
            send_status("error", str(exc))
            send_message(
                "account_result",
                success=False,
                workflow="change_language",
                language=language,
                native_name=None,
                message=str(exc),
                error_type="exception",
            )
            return 1


__all__ = ["AccountChangeLanguageRunnerMixin"]
