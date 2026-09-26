"""Gmail logout runner for the account bridge (the run is the core's `run_gmail_account`)."""

from typing import Any, Callable

from bridges.gmail.account.runtime.persistence import unpersist_gmail_account
from bridges.gmail.account.runtime.workflow_result import finish_account_result
from taktik.core.app.email.gmail.workflows.agent_handler import (
    GMAIL_ACCOUNT_LOGOUT_WORKFLOW_ID,
    run_gmail_account,
)


def run_gmail_logout(
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
    """Run the Gmail logout workflow and unpersist the account on success."""
    email = (config.get("email") or "").strip()
    if not email:
        send_error("email is required for logout")
        return 1

    send_status("running", f"Removing Gmail account {email}...")
    send_log("info", f"Gmail logout workflow - {email}")

    try:
        result = run_gmail_account(
            GMAIL_ACCOUNT_LOGOUT_WORKFLOW_ID,
            {"email": email},
            device=device,
            device_id=device_id,
            notifier=notifier,
            account_unpersister=lambda removed: unpersist_gmail_account(removed, send_log),
        )
        return finish_account_result(
            result,
            workflow_type="logout",
            email=email,
            send_status=send_status,
            send_message=send_message,
        )
    except Exception as exc:  # noqa: BLE001
        import traceback

        send_error(f"Gmail logout error: {exc}")
        send_log("error", traceback.format_exc())
        return 1


__all__ = ["run_gmail_logout"]
