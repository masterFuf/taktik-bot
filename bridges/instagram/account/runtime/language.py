"""Instagram account change-language workflow adapter.

Bridge runner mixin for the ``change_language`` workflowType. Reads the target
language code off the config, runs the core ``ChangeLanguageWorkflow``, and emits
bridge JSON events — including per-step ``change_language_step`` events used by the
desktop Agent panel for live narration. The core workflow stays stdout-free: this
runner injects a notifier callback that maps step callbacks to ``send_message``.
"""

from __future__ import annotations

from bridges.instagram.runtime.ipc import send_error, send_log, send_message, send_status


class AccountChangeLanguageRunnerMixin:
    """Run the Instagram app-language change and emit bridge JSON events."""

    def _run_change_language(self, device) -> int:
        language = self.config.get("language", "")

        if not language:
            send_error("language is required for change_language")
            return 1

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
            from taktik.core.social_media.instagram.workflows.management.language.change_language_workflow import (
                ChangeLanguageWorkflow,
            )

            workflow = ChangeLanguageWorkflow(device, self.device_id, notifier=_emit_step)
            result = workflow.execute(language=language)

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
