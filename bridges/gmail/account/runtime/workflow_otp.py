"""Gmail OTP workflow runner for the account bridge."""

from typing import Any, Callable

from bridges.gmail.account.runtime.workflow_result import finish_account_result
from taktik.core.app.email.gmail.workflows.account import GmailWorkflow


def run_gmail_read_otp(
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
    """Run the Gmail OTP reading workflow."""
    email = (config.get("email") or "").strip()
    sender_filter = config.get("senderFilter") or None
    subject_filter = config.get("subjectFilter") or None
    timeout = int(config.get("timeout") or 120)
    if not email:
        send_error("email is required for read_otp")
        return 1

    send_status("running", f"Reading verification code from {email}...")
    send_log("info", f"Gmail OTP workflow - {email} (sender={sender_filter})")

    try:
        workflow = GmailWorkflow(device, device_id, notifier=notifier)
        result = workflow.get_latest_verification_code(
            email=email,
            sender_filter=sender_filter,
            subject_filter=subject_filter,
            timeout=timeout,
        )
        return finish_account_result(
            result,
            workflow_type="read_otp",
            email=email,
            send_status=send_status,
            send_message=send_message,
            extra={"code": result.get("code")},
        )
    except Exception as exc:  # noqa: BLE001
        import traceback

        send_error(f"Gmail OTP error: {exc}")
        send_log("error", traceback.format_exc())
        return 1


__all__ = ["run_gmail_read_otp"]
