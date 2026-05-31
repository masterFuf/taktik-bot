"""Agent runtime handlers for Instagram account management workflows."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.management.login import LoginWorkflow
from taktik.core.social_media.instagram.workflows.management.logout import LogoutWorkflow
from taktik.core.social_media.instagram.workflows.management.signup import SignupWorkflow


INSTAGRAM_ACCOUNT_LOGIN_WORKFLOW_ID = "instagram.account.login"
INSTAGRAM_ACCOUNT_LOGOUT_WORKFLOW_ID = "instagram.account.logout"
INSTAGRAM_ACCOUNT_REGISTER_WORKFLOW_ID = "instagram.account.register"
INSTAGRAM_ACCOUNT_WORKFLOW_IDS = (
    INSTAGRAM_ACCOUNT_LOGIN_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_LOGOUT_WORKFLOW_ID,
    INSTAGRAM_ACCOUNT_REGISTER_WORKFLOW_ID,
)
WorkflowFactory = Callable[..., Any]


def build_instagram_account_handler(
    *,
    device,
    device_id: str,
    login_workflow_factory: WorkflowFactory = LoginWorkflow,
    logout_workflow_factory: WorkflowFactory = LogoutWorkflow,
    signup_workflow_factory: WorkflowFactory = SignupWorkflow,
) -> WorkflowHandler:
    """Build an injectable Instagram account handler without bridge startup."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = _merge_invocation_payload(invocation, payload)

        if invocation.workflow_id == INSTAGRAM_ACCOUNT_LOGIN_WORKFLOW_ID:
            params = _login_params(merged)
            workflow = login_workflow_factory(device, device_id)
            return workflow.execute(**params)

        if invocation.workflow_id == INSTAGRAM_ACCOUNT_LOGOUT_WORKFLOW_ID:
            workflow = logout_workflow_factory(device, device_id)
            return workflow.execute()

        if invocation.workflow_id == INSTAGRAM_ACCOUNT_REGISTER_WORKFLOW_ID:
            params = _register_params(merged)
            workflow = signup_workflow_factory(device, device_id)
            return workflow.execute(**params)

        raise ValueError(f"Unsupported Instagram account workflow id: {invocation.workflow_id}")

    return handler


def register_instagram_account_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    device_id: str,
    login_workflow_factory: WorkflowFactory = LoginWorkflow,
    logout_workflow_factory: WorkflowFactory = LogoutWorkflow,
    signup_workflow_factory: WorkflowFactory = SignupWorkflow,
) -> WorkflowRegistry:
    """Register Instagram account handlers into an injected Agent registry."""
    handler = build_instagram_account_handler(
        device=device,
        device_id=device_id,
        login_workflow_factory=login_workflow_factory,
        logout_workflow_factory=logout_workflow_factory,
        signup_workflow_factory=signup_workflow_factory,
    )
    for workflow_id in INSTAGRAM_ACCOUNT_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _merge_invocation_payload(
    invocation: WorkflowInvocation,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(payload)
    merged.update(invocation.params)
    return merged


def _login_params(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "username": _required_string(
            payload,
            "username",
            message="Instagram login requires username",
        ),
        "password": _required_string(
            payload,
            "password",
            message="Instagram login requires password",
        ),
        "max_retries": _int_param(payload, "max_retries", "maxRetries", default=3),
        "save_session": _bool_param(payload, "save_session", "saveSession", default=True),
        "use_saved_session": _bool_param(
            payload,
            "use_saved_session",
            "useSavedSession",
            default=True,
        ),
        "save_login_info_instagram": _bool_param(
            payload,
            "save_login_info_instagram",
            "saveLoginInfoInstagram",
            default=False,
        ),
    }


def _register_params(payload: Mapping[str, Any]) -> dict[str, Any]:
    method = _string_param(payload, "method", default="email").lower()
    if method not in {"email", "phone"}:
        raise ValueError("Instagram register method must be 'email' or 'phone'")

    email = _optional_string(payload, "email")
    phone = _optional_string(payload, "phone")
    if method == "email" and not email:
        raise ValueError("Instagram register requires email when method is email")
    if method == "phone" and not phone:
        raise ValueError("Instagram register requires phone when method is phone")

    return {
        "method": method,
        "email": email,
        "phone": phone,
    }


def _required_string(payload: Mapping[str, Any], name: str, *, message: str) -> str:
    value = _optional_string(payload, name)
    if not value:
        raise ValueError(message)
    return value


def _optional_string(payload: Mapping[str, Any], name: str) -> str | None:
    value = payload.get(name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_param(payload: Mapping[str, Any], name: str, *, default: str) -> str:
    value = payload.get(name)
    if value is None:
        return default
    return str(value).strip() or default


def _int_param(payload: Mapping[str, Any], *names: str, default: int) -> int:
    for name in names:
        value = payload.get(name)
        if value is not None:
            return int(value)
    return default


def _bool_param(payload: Mapping[str, Any], *names: str, default: bool) -> bool:
    for name in names:
        value = payload.get(name)
        if value is not None:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)
    return default
