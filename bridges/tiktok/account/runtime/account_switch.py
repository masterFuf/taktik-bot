"""TikTok native account-switch bridge adapter."""

from bridges.tiktok.runtime.ipc import _ipc, send_error, send_log, send_message, send_status


class TikTokAccountSwitchMixin:
    """Run native account switch/list workflows from bridge payloads."""

    def _switch_workflow(self, device):
        from taktik.core.social_media.tiktok.auth.switch import TikTokSwitchAccount

        factory = getattr(self, "_switch_workflow_factory", TikTokSwitchAccount)
        return factory(
            device,
            self.device_id,
            android_user_id=self.android_user_id,
            notifier=_ipc,
        )

    def _emit_account_result(self, result: dict) -> int:
        success = bool(result.get("success"))
        send_status("success" if success else "error", result.get("message", ""))
        send_message("account_result", **result)
        return 0 if success else 1

    def _run_switch_account(self, device) -> int:
        target = (self.config.get("targetUsername") or "").strip()
        if not target:
            send_error("targetUsername is required for switch_account")
            return 1
        send_status("running", f"Verifying TikTok account {target}...")
        send_log("info", f"Native TikTok account switch -> {target}")
        try:
            return self._emit_account_result(self._switch_workflow(device).switch_account(target))
        except Exception as exc:  # noqa: BLE001
            send_error(f"TikTok account switch failed: {exc}")
            return 1

    def _run_list_accounts(self, device) -> int:
        send_status("running", "Reading TikTok's signed-in accounts...")
        try:
            return self._emit_account_result(self._switch_workflow(device).list_accounts())
        except Exception as exc:  # noqa: BLE001
            send_error(f"Could not list TikTok accounts: {exc}")
            return 1


__all__ = ["TikTokAccountSwitchMixin"]
