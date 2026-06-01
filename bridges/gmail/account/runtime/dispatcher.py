"""Workflow dispatcher for the Gmail account bridge."""

from bridges.gmail.account.runtime.workflows import (
    run_gmail_login,
    run_gmail_logout,
    run_gmail_read_otp,
    run_gmail_scan_accounts,
)


def dispatch_gmail_account_workflow(
    *,
    workflow_type: str,
    config: dict,
    session,
    device_id: str,
    notifier,
    send_status,
    send_log,
    send_error,
    send_message,
) -> int:
    """Route a Gmail account workflow while preserving bridge stdout events."""
    if workflow_type == "login":
        return run_gmail_login(
            config=config,
            **_build_common(session, device_id, notifier, send_status, send_log, send_error, send_message),
        )
    if workflow_type == "logout":
        return run_gmail_logout(
            config=config,
            **_build_common(session, device_id, notifier, send_status, send_log, send_error, send_message),
        )
    if workflow_type == "read_otp":
        return run_gmail_read_otp(
            config=config,
            **_build_common(session, device_id, notifier, send_status, send_log, send_error, send_message),
        )
    if workflow_type == "scan_accounts":
        return run_gmail_scan_accounts(
            **_build_common(session, device_id, notifier, send_status, send_log, send_error, send_message),
        )

    send_error(f"Unknown workflowType: {workflow_type}")
    return 1


def _build_common(session, device_id: str, notifier, send_status, send_log, send_error, send_message) -> dict:
    return {
        "device": session.device,
        "device_id": device_id,
        "notifier": notifier,
        "send_status": send_status,
        "send_log": send_log,
        "send_error": send_error,
        "send_message": send_message,
    }


__all__ = ["dispatch_gmail_account_workflow"]
