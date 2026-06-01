"""Workflow runners for the Gmail account bridge."""

from typing import Any, Callable

from bridges.gmail.account.runtime.persistence import (
    persist_gmail_account,
    unpersist_gmail_account,
)
from taktik.core.app.email.gmail.workflows.account import GmailWorkflow


def finish_account_result(
    result: dict,
    *,
    workflow_type: str,
    email: str,
    send_status: Callable[[str, str], None],
    send_message: Callable[..., None],
    extra: dict | None = None,
) -> int:
    """Emit the historical account_result payload for Gmail account flows."""
    success = bool(result.get("success"))
    send_status("success" if success else "error", result.get("message", ""))
    payload = {
        "success": success,
        "workflow": workflow_type,
        "email": email,
        "message": result.get("message", ""),
        "error_type": result.get("error_type"),
    }
    if extra:
        payload.update(extra)
    send_message("account_result", **payload)
    return 0 if success else 1


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
        workflow = GmailWorkflow(device, device_id, notifier=notifier)
        result = workflow.open_account_removal_settings(email=email)
        if result.get("success"):
            unpersist_gmail_account(email, send_log)
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
        workflow = GmailWorkflow(device, device_id, notifier=notifier)
        result = workflow.scan_accounts()
        if result.get("success"):
            for account in result.get("accounts", []):
                email = account.get("email") if isinstance(account, dict) else None
                if email:
                    persist_gmail_account(email, device_id, send_log)
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
