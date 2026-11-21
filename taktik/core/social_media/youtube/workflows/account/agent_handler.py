"""The one launcher of the YouTube account workflows, and their Agent handlers.

`run_youtube_account` is what the account bridge and the handlers registered as
`youtube.account.*` (the CLI) call, once each has read its payload.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.kernel.contracts import WorkflowInvocation
from taktik.core.kernel.handler_params import merge_invocation_payload, required_text_param, text_param
from taktik.core.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.shared.diagnostics.run_door import open_run_door
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


def run_youtube_account(
    workflow_id: str,
    params: Mapping[str, Any],
    *,
    device,
    device_id: str,
    notifier=None,
    account_repository=None,
    workflow_factory: YouTubeAccountWorkflowFactory = YouTubeAccountWorkflow,
) -> dict[str, Any]:
    """Log in or out of YouTube with already-read params. A locked phone or a phone without network
    raises `RunRefused` before the app is touched."""
    if workflow_id not in YOUTUBE_ACCOUNT_WORKFLOW_IDS:
        raise ValueError(f"Unsupported YouTube account workflow id: {workflow_id}")

    # A locked phone or a phone without network does not start its run, from any host (`RunRefused`).
    open_run_door(device_id)
    workflow = workflow_factory(
        device,
        device_id,
        notifier=notifier,
        account_repository=account_repository,
    )
    if workflow_id == YOUTUBE_ACCOUNT_LOGIN_WORKFLOW_ID:
        return workflow.login(
            email=params["email"],
            password=params.get("password", ""),
        )
    # The other id: YOUTUBE_ACCOUNT_LOGOUT_WORKFLOW_ID.
    return workflow.logout(email=params.get("email", ""))


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
        merged = merge_invocation_payload(invocation, payload)
        return run_youtube_account(
            invocation.workflow_id,
            youtube_account_params(invocation.workflow_id, merged),
            device=device,
            device_id=device_id,
            notifier=notifier,
            account_repository=account_repository,
            workflow_factory=workflow_factory,
        )

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


def youtube_account_params(workflow_id: str, payload: Mapping[str, Any]) -> dict[str, str]:
    """The params of `workflow_id` read from a payload.

    Raises ValueError, before any device work, when a required field is missing.
    """
    reader = _READERS.get(workflow_id)
    if reader is None:
        raise ValueError(f"Unsupported YouTube account workflow id: {workflow_id}")
    return reader(payload)


def login_params_from_payload(payload: Mapping[str, Any]) -> dict[str, str]:
    """`youtube.account.login`: the Google account YouTube signs in with."""
    return {
        "email": required_text_param(payload, "email", message="YouTube login requires email"),
        # The workflow takes "" for no password (the account is already on the phone).
        "password": text_param(payload, "password") or "",
    }


def logout_params_from_payload(payload: Mapping[str, Any]) -> dict[str, str]:
    """`youtube.account.logout`: the account to sign out; empty, the one signed in."""
    return {"email": text_param(payload, "email") or ""}


_READERS = {
    YOUTUBE_ACCOUNT_LOGIN_WORKFLOW_ID: login_params_from_payload,
    YOUTUBE_ACCOUNT_LOGOUT_WORKFLOW_ID: logout_params_from_payload,
}
