"""TikTok account login workflow adapter."""

from bridges.tiktok.runtime.ipc import _ipc, send_error, send_log, send_message, send_status


class TikTokAccountLoginMixin:
    """Run TikTok account login from the bridge payload."""

    def _run_login(self, device) -> int:
        username = self.config.get("username", "")
        password = self.config.get("password", "")
        save_session = self.config.get("saveSession", True)
        max_retries = self.config.get("maxRetries", 3)

        if not username or not password:
            send_error("username and password are required for login")
            return 1

        send_status("running", f"Starting login for @{username}...")
        send_log("info", f"Login workflow - @{username}")

        try:
            from taktik.core.social_media.tiktok.workflows.management.login.login_workflow import TikTokLoginWorkflow

            workflow = TikTokLoginWorkflow(device, self.device_id, notifier=_ipc)
            result = workflow.execute(
                username=username,
                password=password,
                max_retries=max_retries,
                save_session=save_session,
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


__all__ = ["TikTokAccountLoginMixin"]
