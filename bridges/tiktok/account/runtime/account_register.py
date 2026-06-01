"""TikTok account registration workflow adapter."""

from bridges.tiktok.runtime.ipc import _ipc, send_error, send_log, send_message, send_status


class TikTokAccountRegisterMixin:
    """Run TikTok account registration from the bridge payload."""

    def _run_register(self, device) -> int:
        method = self.config.get("method", "email")
        email = self.config.get("email", "")
        phone = self.config.get("phone", "")
        phone_country = self.config.get("phoneCountry", "") or None
        gmail_password = self.config.get("gmailPassword", "") or None
        tiktok_password = self.config.get("tiktokPassword") or self.config.get("tiktok_password") or None
        nickname = self.config.get("nickname") or None

        send_status("running", f"Starting register ({method})...")
        send_log("info", f"Register workflow - method={method}")

        try:
            from taktik.core.social_media.tiktok.workflows.management.signup.signup_workflow import TikTokSignupWorkflow

            workflow = TikTokSignupWorkflow(device, self.device_id, notifier=_ipc)
            result = workflow.execute(
                method=method,
                email=email or None,
                phone=phone or None,
                phone_country=phone_country,
                gmail_password=gmail_password,
                tiktok_password=tiktok_password,
                nickname=nickname,
            )
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
