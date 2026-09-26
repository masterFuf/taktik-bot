"""The one launcher of the Gmail account workflows, and their Agent handlers.

`run_gmail_account` is what the Gmail account bridge and the handlers registered as
`gmail.account.*` (the CLI) call, once each has read its payload. Persistence is injected.
"""

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


def run_gmail_account(
    workflow_id: str,
    params: Mapping[str, Any],
    *,
    device,
    device_id: str,
    notifier=None,
    account_persister: AccountPersister | None = None,
    account_unpersister: AccountPersister | None = None,
    workflow_factory: GmailWorkflowFactory = GmailWorkflow,
) -> dict[str, Any]:
    """Run one Gmail account workflow with already-read params, then persist its outcome."""
    workflow = workflow_factory(device, device_id, notifier=notifier)

    if workflow_id == GMAIL_ACCOUNT_LOGIN_WORKFLOW_ID:
        result = workflow.ensure_account_added(**params)
        if result.get("success") and account_persister is not None:
            account_persister(params["email"])
        return result

    if workflow_id == GMAIL_ACCOUNT_LOGOUT_WORKFLOW_ID:
        result = workflow.open_account_removal_settings(**params)
        if result.get("success") and account_unpersister is not None:
            account_unpersister(params["email"])
        return result

    if workflow_id == GMAIL_ACCOUNT_READ_OTP_WORKFLOW_ID:
        return workflow.get_latest_verification_code(**params)

    if workflow_id == GMAIL_ACCOUNT_SCAN_ACCOUNTS_WORKFLOW_ID:
        result = workflow.scan_accounts()
        if result.get("success") and account_persister is not None:
            for account in result.get("accounts", []):
                email = account.get("email") if isinstance(account, Mapping) else None
                if email:
                    account_persister(str(email))
        return result

    raise ValueError(f"Unsupported Gmail account workflow id: {workflow_id}")


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

    readers = {
        GMAIL_ACCOUNT_LOGIN_WORKFLOW_ID: _login_params,
        GMAIL_ACCOUNT_LOGOUT_WORKFLOW_ID: _logout_params,
        GMAIL_ACCOUNT_READ_OTP_WORKFLOW_ID: _read_otp_params,
        GMAIL_ACCOUNT_SCAN_ACCOUNTS_WORKFLOW_ID: lambda _payload: {},
    }

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        read = readers.get(invocation.workflow_id)
        if read is None:
            raise ValueError(f"Unsupported Gmail account workflow id: {invocation.workflow_id}")
        return run_gmail_account(
            invocation.workflow_id,
            read(merge_invocation_payload(invocation, payload)),
            device=device,
            device_id=device_id,
            notifier=notifier,
            account_persister=account_persister,
            account_unpersister=account_unpersister,
            workflow_factory=workflow_factory,
        )

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
