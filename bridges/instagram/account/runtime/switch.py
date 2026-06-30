"""Instagram account switch (multi-account) workflow adapter."""

from __future__ import annotations

from bridges.instagram.runtime.ipc import send_error, send_log, send_message, send_status


class AccountSwitchRunnerMixin:
    """Run an Instagram account switch and emit bridge JSON events."""

    def _run_switch(self, device) -> int:
        target = (self.config.get("targetUsername") or "").strip()
        send_status("running", f"Switching account to @{target}…" if target else "Switching account…")
        send_log("info", "Switch-account workflow")

        if not target:
            send_error("targetUsername is required for switch_account")
            return 1

        try:
            from taktik.core.social_media.instagram.workflows.management.switch import (
                SwitchAccountWorkflow,
            )

            # Forward live progress lines as running status updates.
            def _notify(message: str) -> None:
                send_status("running", message)

            workflow = SwitchAccountWorkflow(device, self.device_id, notifier=_notify)
            result = workflow.execute(target)

            outcome = "success" if result["success"] else "error"
            send_status(outcome, result.get("message", ""))

            # Surface the accounts seen on the device picker so the front can refresh its list.
            detected = result.get("detected_accounts") or []
            if detected:
                send_message("accounts_detected", accounts=detected)

            send_message(
                "account_result",
                success=result["success"],
                workflow="switch_account",
                message=result.get("message", ""),
                error_type=result.get("error_type"),
                switched_to=result.get("switched_to"),
                relogin_required=result.get("relogin_required", False),
                detected_accounts=detected,
            )
            return 0 if result["success"] else 1
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"Switch error: {exc}")
            send_log("error", traceback.format_exc())
            return 1


__all__ = ["AccountSwitchRunnerMixin"]
