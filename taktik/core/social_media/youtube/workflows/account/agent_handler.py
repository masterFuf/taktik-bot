"""Agent runtime handlers for YouTube account workflows."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.youtube.workflows.account.account_workflow import (
    YouTubeAccountWorkflow,
)


YOUTUBE_ACCOUNT_LOGIN_WORKFLOW_ID = "youtube.account.login"
YOUTUBE_ACCOUNT_LOGOUT_WORKFLOW_ID = "youtube.account.logout"
YOUTUBE_ACCOUNT_WORKFLOW_IDS = (
    YOUTUBE_ACCOUNT_LOGIN_WORKFLOW_ID,
    YOUTUBE_ACCOUNT_LOGOUT_WORKFLOW_ID,
)
YouTubeAccountWorkflowFactory = Callable[..., Any]


def build_youtube_account_handler(
    *,
    device,
    device_id: str,
    notifier=None,
    workflow_factory: YouTubeAccountWorkflowFactory = YouTubeAccountWorkflow,
    account_repository=None,
) -> WorkflowHandler:
    """Build an injectable YouTube account handler without bridge startup."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        params = _account_params(invocation, payload)
        workflow = workflow_factory(
            device,
            device_id,
            notifier=notifier,
            account_repository=account_repository,
        )

        if invocation.workflow_id == YOUTUBE_ACCOUNT_LOGIN_WORKFLOW_ID:
            return workflow.login(
                email=params["email"],
                password=params.get("password", ""),
            )
        if invocation.workflow_id == YOUTUBE_ACCOUNT_LOGOUT_WORKFLOW_ID:
            return workflow.logout(email=params.get("email", ""))

        raise ValueError(f"Unsupported YouTube account workflow id: {invocation.workflow_id}")

    return handler


def register_youtube_account_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    device_id: str,
    notifier=None,
    workflow_factory: YouTubeAccountWorkflowFactory = YouTubeAccountWorkflow,
    account_repository=None,
) -> WorkflowRegistry:
    """Register YouTube account handlers into an injected Agent registry."""
    handler = build_youtube_account_handler(
        device=device,
        device_id=device_id,
        notifier=notifier,
        workflow_factory=workflow_factory,
        account_repository=account_repository,
    )
    for workflow_id in YOUTUBE_ACCOUNT_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _account_params(invocation: WorkflowInvocation, payload: Mapping[str, Any]) -> dict[str, str]:
    merged = dict(payload)
    merged.update(invocation.params)

    if invocation.workflow_id == YOUTUBE_ACCOUNT_LOGIN_WORKFLOW_ID:
        email = _required_string(merged, "email", message="YouTube login requires email")
        return {
            "email": email,
            "password": _optional_string(merged, "password"),
        }

    if invocation.workflow_id == YOUTUBE_ACCOUNT_LOGOUT_WORKFLOW_ID:
        return {"email": _optional_string(merged, "email")}

    raise ValueError(f"Unsupported YouTube account workflow id: {invocation.workflow_id}")


def _required_string(payload: Mapping[str, Any], name: str, *, message: str) -> str:
    value = _optional_string(payload, name)
    if not value:
        raise ValueError(message)
    return value


def _optional_string(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if value is None:
        return ""
    return str(value).strip()
