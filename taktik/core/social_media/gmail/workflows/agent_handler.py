"""The one launcher of the Gmail account workflows, and their Agent handlers.

`run_gmail_account` is what the Gmail account bridge and the handlers registered as
`gmail.account.*` (the CLI) call, once each has read its payload. Persistence is injected.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.kernel.contracts import WorkflowInvocation
from taktik.core.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.kernel.handler_params import (
    merge_invocation_payload,
    value_param,
)
from taktik.core.social_media.gmail.workflows.account import GmailWorkflow


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

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        return run_gmail_account(
            invocation.workflow_id,
            gmail_account_params(invocation.workflow_id, merge_invocation_payload(invocation, payload)),
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


def gmail_account_params(workflow_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """The params of `workflow_id` read from a payload (page keys or snake_case).

    Raises ValueError, before any device work, when a required field is missing.
    """
    reader = _READERS.get(workflow_id)
    if reader is None:
        raise ValueError(f"Unsupported Gmail account workflow id: {workflow_id}")
    return reader(payload)


def login_params_from_payload(payload: Mapping[str, Any]) -> dict[str, str]:
    """`gmail.account.login`: the Google account to add to the phone."""
    return {
        "email": _required_string(payload, "email", message="Gmail login requires email"),
        "password": _required_string(payload, "password", message="Gmail login requires password"),
    }


def logout_params_from_payload(payload: Mapping[str, Any]) -> dict[str, str]:
    """`gmail.account.logout`: the Google account to remove."""
    return {
        "email": _required_string(payload, "email", message="Gmail logout requires email"),
    }


def read_otp_params_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """`gmail.account.read_otp`: whose inbox, which mail, and how long to wait for it."""
    return {
        "email": _required_string(payload, "email", message="Gmail read_otp requires email"),
        "sender_filter": _optional_string(payload, "senderFilter", "sender_filter"),
        "subject_filter": _optional_string(payload, "subjectFilter", "subject_filter"),
        # A zero or empty timeout waits the default time rather than not at all.
        "timeout": int(value_param(payload, "timeout", default=None) or 120),
    }


def scan_accounts_params_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """`gmail.account.scan_accounts` takes nothing: it reads what the phone holds."""
    return {}


_READERS = {
    GMAIL_ACCOUNT_LOGIN_WORKFLOW_ID: login_params_from_payload,
    GMAIL_ACCOUNT_LOGOUT_WORKFLOW_ID: logout_params_from_payload,
    GMAIL_ACCOUNT_READ_OTP_WORKFLOW_ID: read_otp_params_from_payload,
    GMAIL_ACCOUNT_SCAN_ACCOUNTS_WORKFLOW_ID: scan_accounts_params_from_payload,
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
