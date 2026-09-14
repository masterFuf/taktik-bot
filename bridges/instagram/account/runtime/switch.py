"""Instagram account switch (multi-account) workflow adapter."""

from __future__ import annotations

from bridges.instagram.runtime.ipc import send_error, send_log, send_message, send_status


class AccountSwitchRunnerMixin:
    """Run an Instagram account switch and emit bridge JSON events."""

    def _account_workflow(self, device, workflow_name: str):
        from taktik.core.social_media.instagram.workflows.management.switch import (
            SwitchAccountWorkflow,
        )

        def _notify(message: str) -> None:
            send_status("running", message)

        def _emit_active(username: str) -> None:
            send_message("active_account_detected", username=username, workflow=workflow_name)

        def _emit_step(step: str, data: dict) -> None:
            send_message("account_step", step=step, workflow=workflow_name, **data)

        factory = getattr(self, "_switch_workflow_factory", SwitchAccountWorkflow)
        return factory(
            device,
            self.device_id,
            notifier=_notify,
            on_active_account=_emit_active,
            on_step=_emit_step,
        )

    def _run_switch(self, device) -> int:
        target = (self.config.get("targetUsername") or "").strip()
        send_status("running", f"Switching account to @{target}…" if target else "Switching account…")
        send_log("info", "Switch-account workflow")

        if not target:
            send_error("targetUsername is required for switch_account")
            return 1

        try:
            workflow = self._account_workflow(device, "switch_account")
            result = workflow.execute(target)

            outcome = "success" if result["success"] else "error"
            send_status(outcome, result.get("message", ""))

            # Surface the accounts seen on the device picker so the front can refresh its list.
            detected = result.get("detected_accounts") or []
            if detected:
                send_message("accounts_detected", accounts=detected)
                # Complete picker set → the front persists it as the device's saved-accounts history.
                send_message("saved_accounts_detected", accounts=detected)

            send_message(
                "account_result",
                success=result["success"],
                workflow="switch_account",
                message=result.get("message", ""),
                error_type=result.get("error_type"),
                switched_to=result.get("switched_to"),
                relogin_required=result.get("relogin_required", False),
                detected_accounts=detected,
                requested_username=result.get("requested_username"),
                active_username=result.get("active_username"),
                previous_username=result.get("previous_username"),
                already_active=result.get("already_active", False),
                attempts=result.get("attempts", 0),
                failure_stage=result.get("failure_stage"),
                failure_category=result.get("failure_category"),
                state_known=result.get("state_known", False),
            )
            return 0 if result["success"] else 1
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"Switch error: {exc}")
            send_log("error", traceback.format_exc())
            return 1

    def _run_list_accounts(self, device) -> int:
        send_status("running", "Reading connected accounts…")
        send_log("info", "List-accounts workflow")
        try:
            workflow = self._account_workflow(device, "list_accounts")
            result = workflow.list_accounts()

            accounts = result.get("accounts") or []
            send_message("accounts_detected", accounts=accounts)
            send_status("success", result.get("message", ""))
            send_message(
                "account_result",
                success=result["success"],
                workflow="list_accounts",
                message=result.get("message", ""),
                detected_accounts=accounts,
            )
            return 0
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"List-accounts error: {exc}")
            send_log("error", traceback.format_exc())
            return 1

    def _run_list_saved_accounts(self, device) -> int:
        send_status("running", "Listing all saved accounts (logging out to open the picker)…")
        send_log("info", "List-saved-accounts workflow")
        try:
            workflow = self._account_workflow(device, "list_saved_accounts")
            result = workflow.list_saved_accounts()

            accounts = result.get("accounts") or []
            send_message("accounts_detected", accounts=accounts)
            # Complete picker set → the front persists it as the device's saved-accounts history.
            send_message("saved_accounts_detected", accounts=accounts)
            send_status("success", result.get("message", ""))
            send_message(
                "account_result",
                success=result["success"],
                workflow="list_saved_accounts",
                message=result.get("message", ""),
                detected_accounts=accounts,
            )
            return 0
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"List-saved-accounts error: {exc}")
            send_log("error", traceback.format_exc())
            return 1


__all__ = ["AccountSwitchRunnerMixin"]
