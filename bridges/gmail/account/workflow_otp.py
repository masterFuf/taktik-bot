"""Gmail OTP runner for the account bridge (the run is the core's `run_gmail_account`)."""

from typing import Any, Callable

from bridges.gmail.account.workflow_result import finish_account_result
from taktik.core.social_media.gmail.workflows.agent_handler import (
    GMAIL_ACCOUNT_READ_OTP_WORKFLOW_ID,
    read_otp_params_from_payload,
    run_gmail_account,
)


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
    try:
        params = read_otp_params_from_payload(config)
    except ValueError as exc:
        send_error(str(exc))
        return 1
    email = params["email"]

    send_status("running", f"Reading verification code from {email}...")
    send_log("info", f"Gmail OTP workflow - {email} (sender={params['sender_filter']})")

    try:
        result = run_gmail_account(
            GMAIL_ACCOUNT_READ_OTP_WORKFLOW_ID,
            params,
            device=device,
            device_id=device_id,
            notifier=notifier,
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
