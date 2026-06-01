"""Instagram account registration workflow adapter."""

from __future__ import annotations

from bridges.instagram.runtime.ipc import send_error, send_log, send_message, send_status


class AccountRegisterRunnerMixin:
    """Run Instagram registration and emit bridge JSON events."""

    def _run_register(self, device) -> int:
        method = self.config.get("method", "email")
        email = self.config.get("email", "")
        phone = self.config.get("phone", "")

        send_status("running", f"Starting register ({method})...")
        send_log("info", f"Register workflow - method={method}")

        try:
            from taktik.core.social_media.instagram.workflows.management.signup.signup_workflow import SignupWorkflow

            workflow = SignupWorkflow(device, self.device_id)
            result = workflow.execute(method=method, email=email or None, phone=phone or None)
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


__all__ = ["AccountRegisterRunnerMixin"]
