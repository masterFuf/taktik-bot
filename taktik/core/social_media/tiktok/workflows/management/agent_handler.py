"""Agent runtime handlers for TikTok account management workflows."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    bool_param,
    int_param,
    merge_invocation_payload,
    value_param,
)
from taktik.core.social_media.tiktok.workflows.management.login.login_workflow import (
    TikTokLoginWorkflow,
)
from taktik.core.social_media.tiktok.workflows.management.logout.logout_workflow import (
    TikTokLogoutWorkflow,
)
from taktik.core.social_media.tiktok.workflows.management.signup.signup_workflow import (
    TikTokSignupWorkflow,
)


TIKTOK_ACCOUNT_LOGIN_WORKFLOW_ID = "tiktok.account.login"
TIKTOK_ACCOUNT_LOGOUT_WORKFLOW_ID = "tiktok.account.logout"
TIKTOK_ACCOUNT_REGISTER_WORKFLOW_ID = "tiktok.account.register"
TIKTOK_ACCOUNT_WORKFLOW_IDS = (
    TIKTOK_ACCOUNT_LOGIN_WORKFLOW_ID,
    TIKTOK_ACCOUNT_LOGOUT_WORKFLOW_ID,
    TIKTOK_ACCOUNT_REGISTER_WORKFLOW_ID,
)
WorkflowFactory = Callable[..., Any]


def build_tiktok_account_handler(
    *,
    device,
    device_id: str,
    notifier=None,
    login_workflow_factory: WorkflowFactory = TikTokLoginWorkflow,
    logout_workflow_factory: WorkflowFactory = TikTokLogoutWorkflow,
    signup_workflow_factory: WorkflowFactory = TikTokSignupWorkflow,
) -> WorkflowHandler:
    """Build an injectable TikTok account handler without bridge startup."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = merge_invocation_payload(invocation, payload)

        if invocation.workflow_id == TIKTOK_ACCOUNT_LOGIN_WORKFLOW_ID:
            params = _login_params(merged)
            workflow = login_workflow_factory(device, device_id, notifier=notifier)
            return workflow.execute(**params)

        if invocation.workflow_id == TIKTOK_ACCOUNT_LOGOUT_WORKFLOW_ID:
            workflow = logout_workflow_factory(device, device_id, notifier=notifier)
            return workflow.execute()

        if invocation.workflow_id == TIKTOK_ACCOUNT_REGISTER_WORKFLOW_ID:
            params = _register_params(merged)
            workflow = signup_workflow_factory(device, device_id, notifier=notifier)
            return workflow.execute(**params)

        raise ValueError(f"Unsupported TikTok account workflow id: {invocation.workflow_id}")

    return handler


def register_tiktok_account_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    device_id: str,
    notifier=None,
    login_workflow_factory: WorkflowFactory = TikTokLoginWorkflow,
    logout_workflow_factory: WorkflowFactory = TikTokLogoutWorkflow,
    signup_workflow_factory: WorkflowFactory = TikTokSignupWorkflow,
) -> WorkflowRegistry:
    """Register TikTok account handlers into an injected Agent registry."""
    handler = build_tiktok_account_handler(
        device=device,
        device_id=device_id,
        notifier=notifier,
        login_workflow_factory=login_workflow_factory,
        logout_workflow_factory=logout_workflow_factory,
        signup_workflow_factory=signup_workflow_factory,
    )
    for workflow_id in TIKTOK_ACCOUNT_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _login_params(payload: Mapping[str, Any]) -> dict[str, Any]:
    username = _required_string(payload, "username", message="TikTok login requires username")
    password = _required_string(payload, "password", message="TikTok login requires password")
    return {
        "username": username,
        "password": password,
        "max_retries": int_param(payload, "max_retries", "maxRetries", default=3),
        "save_session": bool_param(payload, "save_session", "saveSession", default=True),
    }


def _register_params(payload: Mapping[str, Any]) -> dict[str, Any]:
    method = str(value_param(payload, "method", default="email")).strip().lower()
    if method not in {"email", "phone"}:
        raise ValueError("TikTok register method must be 'email' or 'phone'")

    email = _optional_string(payload, "email")
    phone = _optional_string(payload, "phone")
    if method == "email" and not email:
        raise ValueError("TikTok register requires email when method is email")
    if method == "phone" and not phone:
        raise ValueError("TikTok register requires phone when method is phone")

    return {
        "method": method,
        "email": email,
        "phone": phone,
        "phone_country": _optional_string(payload, "phone_country", "phoneCountry"),
        "birth_year": int_param(payload, "birth_year", "birthYear", default=1995),
        "birth_month": int_param(payload, "birth_month", "birthMonth", default=6),
        "birth_day": int_param(payload, "birth_day", "birthDay", default=15),
        "gmail_password": _optional_string(payload, "gmail_password", "gmailPassword"),
        "tiktok_password": _optional_string(payload, "tiktok_password", "tiktokPassword"),
        "nickname": _optional_string(payload, "nickname"),
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
