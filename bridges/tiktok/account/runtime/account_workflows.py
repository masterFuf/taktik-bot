"""Workflow adapters for TikTok account bridge actions."""

from bridges.tiktok.base import _ipc, send_error, send_log, send_message, send_status


class TikTokAccountWorkflowMixin:
    """Dispatch account bridge payloads to TikTok core workflows."""

    def _run_login(self, device) -> int:
        username = self.config.get("username", "")
        password = self.config.get("password", "")
        save_session = self.config.get("saveSession", True)
        max_retries = self.config.get("maxRetries", 3)

        if not username or not password:
            send_error("username and password are required for login")
            return 1

        send_status("running", f"Starting login for @{username}...")
        send_log("info", f"🔐 Login workflow — @{username}")

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
        except Exception as e:
            import traceback

            send_error(f"Login error: {e}")
            send_log("error", traceback.format_exc())
            return 1

    def _run_logout(self, device) -> int:
        send_status("running", "Starting logout...")
        send_log("info", "🚪 Logout workflow")

        try:
            from taktik.core.social_media.tiktok.workflows.management.logout.logout_workflow import TikTokLogoutWorkflow

            workflow = TikTokLogoutWorkflow(device, self.device_id, notifier=_ipc)
            result = workflow.execute()
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
        except Exception as e:
            import traceback

            send_error(f"Logout error: {e}")
            send_log("error", traceback.format_exc())
            return 1

    def _run_register(self, device) -> int:
        method = self.config.get("method", "email")
        email = self.config.get("email", "")
        phone = self.config.get("phone", "")
        phone_country = self.config.get("phoneCountry", "") or None
        gmail_password = self.config.get("gmailPassword", "") or None
        tiktok_password = self.config.get("tiktokPassword") or self.config.get("tiktok_password") or None
        nickname = self.config.get("nickname") or None

        send_status("running", f"Starting register ({method})...")
        send_log("info", f"📝 Register workflow — method={method}")

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
        except Exception as e:
            import traceback

            send_error(f"Register error: {e}")
            send_log("error", traceback.format_exc())
            return 1
