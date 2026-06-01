"""Instagram account login workflow adapter."""

from __future__ import annotations

from bridges.instagram.runtime.ipc import send_error, send_log, send_message, send_status


class AccountLoginRunnerMixin:
    """Run Instagram login and emit bridge JSON events."""

    def _run_login(self, device) -> int:
        username = self.config.get("username", "")
        password = self.config.get("password", "")
        save_session = self.config.get("saveSession", True)
        save_login_info_instagram = self.config.get("saveLoginInfoInstagram", False)
        max_retries = self.config.get("maxRetries", 3)

        if not username or not password:
            send_error("username and password are required for login")
            return 1

        send_status("running", f"Starting login for @{username}...")
        send_log("info", f"Login workflow - @{username}")

        try:
            from taktik.core.social_media.instagram.workflows.management.login.login_workflow import LoginWorkflow

            workflow = LoginWorkflow(device, self.device_id)
            result = workflow.execute(
                username=username,
                password=password,
                max_retries=max_retries,
                save_session=save_session,
                use_saved_session=True,
                save_login_info_instagram=save_login_info_instagram,
            )
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


__all__ = ["AccountLoginRunnerMixin"]
