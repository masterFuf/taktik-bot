"""Gmail account scan runner for the account bridge (the run is the core's `run_gmail_account`)."""

from typing import Any, Callable

from bridges.gmail.account.runtime.persistence import persist_gmail_account
from taktik.core.app.email.gmail.workflows.agent_handler import (
    GMAIL_ACCOUNT_SCAN_ACCOUNTS_WORKFLOW_ID,
    run_gmail_account,
)


def run_gmail_scan_accounts(
    *,
    device: Any,
    device_id: str,
    notifier: Any,
    send_status: Callable[[str, str], None],
    send_log: Callable[[str, str], None],
    send_error: Callable[[str], None],
    send_message: Callable[..., None],
) -> int:
    """Run Gmail account scanning and persist discovered accounts."""
    send_status("running", "Scanning Gmail accounts...")
    send_log("info", "Gmail scan_accounts workflow")

    try:
        result = run_gmail_account(
            GMAIL_ACCOUNT_SCAN_ACCOUNTS_WORKFLOW_ID,
            {},
            device=device,
            device_id=device_id,
            notifier=notifier,
            account_persister=lambda found: persist_gmail_account(found, device_id, send_log),
        )
        success = bool(result.get("success"))
        send_status("success" if success else "error", result.get("message", ""))
        send_message(
            "account_result",
            success=success,
            workflow="scan_accounts",
            accounts=result.get("accounts", []),
            message=result.get("message", ""),
            error_type=result.get("error_type"),
        )
        return 0 if success else 1
    except Exception as exc:  # noqa: BLE001
        import traceback

        send_error(f"Gmail scan_accounts error: {exc}")
        send_log("error", traceback.format_exc())
        return 1


__all__ = ["run_gmail_scan_accounts"]
