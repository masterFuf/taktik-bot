"""Gmail login workflow runner for the account bridge."""

from typing import Any, Callable

from bridges.gmail.account.runtime.persistence import persist_gmail_account
from bridges.gmail.account.runtime.workflow_result import finish_account_result
from taktik.core.app.email.gmail.workflows.account import GmailWorkflow


def run_gmail_login(
    *,
    config: dict,
    device: Any,
    device_id: str,
    notifier: Any,
    send_status: Callable[[str, str], None],
    send_log: Callable[[str, str], None],
    send_error: Callable[[str], None],
    send_message: Callable[..., None],
) -> int:
    """Run the Gmail login workflow and persist the account on success."""
    email = (config.get("email") or "").strip()
    password = config.get("password") or ""
    if not email or not password:
        send_error("email and password are required for login")
        return 1

    send_status("running", f"Adding Gmail account {email}...")
    send_log("info", f"Gmail login workflow - {email}")

    try:
        workflow = GmailWorkflow(device, device_id, notifier=notifier)
        result = workflow.ensure_account_added(email, password)
        if result.get("success"):
            persist_gmail_account(email, device_id, send_log)
        return finish_account_result(
            result,
            workflow_type="login",
            email=email,
            send_status=send_status,
            send_message=send_message,
        )
    except Exception as exc:  # noqa: BLE001
        import traceback

        send_error(f"Gmail login error: {exc}")
        send_log("error", traceback.format_exc())
        return 1


__all__ = ["run_gmail_login"]
