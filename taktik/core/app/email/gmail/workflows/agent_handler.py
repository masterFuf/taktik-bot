"""Agent runtime handlers for Gmail account workflows."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    int_param,
    merge_invocation_payload,
    value_param,
)
from taktik.core.app.email.gmail.workflows.account import GmailWorkflow


GMAIL_ACCOUNT_LOGIN_WORKFLOW_ID = "gmail.account.login"
GMAIL_ACCOUNT_LOGOUT_WORKFLOW_ID = "gmail.account.logout"
GMAIL_ACCOUNT_READ_OTP_WORKFLOW_ID = "gmail.account.read_otp"
GMAIL_ACCOUNT_SCAN_ACCOUNTS_WORKFLOW_ID = "gmail.account.scan_accounts"
GMAIL_ACCOUNT_WORKFLOW_IDS = (
    GMAIL_ACCOUNT_LOGIN_WORKFLOW_ID,
    GMAIL_ACCOUNT_LOGOUT_WORKFLOW_ID,
    GMAIL_ACCOUNT_READ_OTP_WORKFLOW_ID,
    GMAIL_ACCOUNT_SCAN_ACCOUNTS_WORKFLOW_ID,
)
GmailWorkflowFactory = Callable[..., Any]
AccountPersister = Callable[[str], None]


def build_gmail_account_handler(
    *,
    device,
    device_id: str,
    notifier=None,
    account_persister: AccountPersister | None = None,
    account_unpersister: AccountPersister | None = None,
    workflow_factory: GmailWorkflowFactory = GmailWorkflow,
) -> WorkflowHandler:
    """Build an injectable Gmail account handler without bridge DB ownership."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = merge_invocation_payload(invocation, payload)

        if invocation.workflow_id == GMAIL_ACCOUNT_LOGIN_WORKFLOW_ID:
            params = _login_params(merged)
            workflow = workflow_factory(device, device_id, notifier=notifier)
            result = workflow.ensure_account_added(**params)
            if result.get("success") and account_persister is not None:
                account_persister(params["email"])
            return result

        if invocation.workflow_id == GMAIL_ACCOUNT_LOGOUT_WORKFLOW_ID:
            params = _logout_params(merged)
            workflow = workflow_factory(device, device_id, notifier=notifier)
            result = workflow.open_account_removal_settings(**params)
            if result.get("success") and account_unpersister is not None:
                account_unpersister(params["email"])
            return result

        if invocation.workflow_id == GMAIL_ACCOUNT_READ_OTP_WORKFLOW_ID:
            params = _read_otp_params(merged)
            workflow = workflow_factory(device, device_id, notifier=notifier)
            return workflow.get_latest_verification_code(**params)

        if invocation.workflow_id == GMAIL_ACCOUNT_SCAN_ACCOUNTS_WORKFLOW_ID:
            workflow = workflow_factory(device, device_id, notifier=notifier)
            result = workflow.scan_accounts()
            if result.get("success") and account_persister is not None:
                for account in result.get("accounts", []):
                    email = account.get("email") if isinstance(account, Mapping) else None
                    if email:
                        account_persister(str(email))
            return result

        raise ValueError(f"Unsupported Gmail account workflow id: {invocation.workflow_id}")

    return handler


def register_gmail_account_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    device_id: str,
    notifier=None,
    account_persister: AccountPersister | None = None,
    account_unpersister: AccountPersister | None = None,
    workflow_factory: GmailWorkflowFactory = GmailWorkflow,
) -> WorkflowRegistry:
    """Register Gmail account handlers into an injected Agent registry."""
    handler = build_gmail_account_handler(
        device=device,
        device_id=device_id,
        notifier=notifier,
        account_persister=account_persister,
        account_unpersister=account_unpersister,
        workflow_factory=workflow_factory,
    )
    for workflow_id in GMAIL_ACCOUNT_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _login_params(payload: Mapping[str, Any]) -> dict[str, str]:
    return {
        "email": _required_string(payload, "email", message="Gmail login requires email"),
        "password": _required_string(payload, "password", message="Gmail login requires password"),
    }


def _logout_params(payload: Mapping[str, Any]) -> dict[str, str]:
    return {
        "email": _required_string(payload, "email", message="Gmail logout requires email"),
    }


def _read_otp_params(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "email": _required_string(payload, "email", message="Gmail read_otp requires email"),
        "sender_filter": _optional_string(payload, "sender_filter", "senderFilter"),
        "subject_filter": _optional_string(payload, "subject_filter", "subjectFilter"),
        "timeout": int_param(payload, "timeout", default=120),
    }


def _required_string(payload: Mapping[str, Any], *names: str, message: str) -> str:
    value = _optional_string(payload, *names)
    if not value:
        raise ValueError(message)
    return value


def _optional_string(payload: Mapping[str, Any], *names: str) -> str | None:
    value = value_param(payload, *names, default=None)
    if value is None:
        return None
    text = str(value).strip()
    return text or None
