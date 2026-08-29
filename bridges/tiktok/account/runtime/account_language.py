"""TikTok app-language change adapter.

Mirrors the logout adapter exactly: the bridge layer converts a payload into a workflow call and
an `account_result` message, and owns none of the UI logic.
"""

from bridges.tiktok.runtime.ipc import _ipc, send_error, send_log, send_message, send_status


class TikTokAccountLanguageMixin:
    """Run the TikTok app-language change from the bridge payload."""

    def _run_change_language(self, device) -> int:
        target = (self.config.get("targetLanguage") or self.config.get("language") or "").strip()
        if not target:
            # Refused here rather than defaulted: silently picking a language would change what
            # the operator's phone speaks on the strength of a missing field.
            send_error("targetLanguage is required (e.g. 'fr', 'en', 'en-US')")
            return 1

        send_status("running", f"Switching the app language to {target}...")
        send_log("info", f"Change language workflow -> {target}")

        try:
            from taktik.core.social_media.tiktok.workflows.management.language import (
                TikTokChangeLanguageWorkflow,
            )

            workflow = TikTokChangeLanguageWorkflow(device, self.device_id, notifier=_ipc)
            result = workflow.run(target)
            outcome = "success" if result["success"] else "error"
            send_status(outcome, result.get("error") or f"language: {result.get('language_after')}")
            send_message(
                "account_result",
                success=result["success"],
                workflow="change_language",
                message=result.get("error") or "",
                error_type=result.get("error_type"),
                # Both languages travel: "changed" and "was already there" are different facts,
                # and a caller that only sees success cannot tell them apart.
                language_before=result.get("language_before"),
                language_after=result.get("language_after"),
                already_set=result.get("already_set", False),
            )
            return 0 if result["success"] else 1
        except Exception as exc:  # noqa: BLE001
            import traceback

            send_error(f"Change language error: {exc}")
            send_log("error", traceback.format_exc())
            return 1


__all__ = ["TikTokAccountLanguageMixin"]
