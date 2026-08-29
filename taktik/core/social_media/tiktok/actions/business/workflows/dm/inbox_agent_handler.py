"""Agent runtime handlers for the TikTok inbox workflows (new followers, unreplied, requests,
activity).

These four workflows existed only as bridge runners: reachable from Electron, unreachable by their
canonical id from the CLI or from an Agent plan. The runners themselves cannot be called here --
they own bridge concerns (startup, `set_workflow`, stdout status events) and return a bare boolean,
throwing away the very data an Agent step needs. What they actually do is drive `DMWorkflow`, so
that is what this module reuses: the same class, the same methods, the same config keys the front
already sends (`mode`, `maxItems`, `usernames`, `decisions`, `onlyUnreplied`,
`delayBetweenActions`), with the read results returned instead of only emitted.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    bool_param,
    float_param,
    int_param,
    list_param,
    merge_invocation_payload,
    notify,
    value_param,
)
from taktik.core.social_media.tiktok.actions.business.workflows.dm.models import DMConfig
from taktik.core.social_media.tiktok.actions.business.workflows.dm.workflow import DMWorkflow


TIKTOK_NEW_FOLLOWERS_WORKFLOW_ID = "tiktok.automation.new_followers"
TIKTOK_DM_UNREPLIED_WORKFLOW_ID = "tiktok.automation.dm_unreplied"
TIKTOK_DM_REQUESTS_WORKFLOW_ID = "tiktok.automation.dm_requests"
TIKTOK_DM_ACTIVITY_WORKFLOW_ID = "tiktok.automation.dm_activity"
TIKTOK_INBOX_WORKFLOW_IDS = (
    TIKTOK_NEW_FOLLOWERS_WORKFLOW_ID,
    TIKTOK_DM_UNREPLIED_WORKFLOW_ID,
    TIKTOK_DM_REQUESTS_WORKFLOW_ID,
    TIKTOK_DM_ACTIVITY_WORKFLOW_ID,
)
DMWorkflowFactory = Callable[..., Any]


def build_tiktok_inbox_handler(
    *,
    device,
    notifier=None,
    workflow_factory: DMWorkflowFactory = DMWorkflow,
) -> WorkflowHandler:
    """Build an injectable inbox handler covering the four inbox workflow ids."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        workflow_id = invocation.workflow_id
        if workflow_id not in TIKTOK_INBOX_WORKFLOW_IDS:
            raise ValueError(f"Unsupported TikTok inbox workflow id: {workflow_id}")

        merged = merge_invocation_payload(invocation, payload)
        workflow = workflow_factory(device, _inbox_config(workflow_id, merged))
        _attach_callbacks(workflow, notifier)
        mode = str(value_param(merged, "mode", default="scrape")).strip() or "scrape"

        if workflow_id == TIKTOK_NEW_FOLLOWERS_WORKFLOW_ID:
            return _run_new_followers(workflow, merged, mode)
        if workflow_id == TIKTOK_DM_UNREPLIED_WORKFLOW_ID:
            return _run_unreplied(workflow, merged)
        if workflow_id == TIKTOK_DM_REQUESTS_WORKFLOW_ID:
            return _run_message_requests(workflow, merged, mode)
        return _run_activity(workflow, merged)

    return handler


def register_tiktok_inbox_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    notifier=None,
    workflow_factory: DMWorkflowFactory = DMWorkflow,
) -> WorkflowRegistry:
    """Register the four TikTok inbox handlers into an injected Agent registry."""
    handler = build_tiktok_inbox_handler(
        device=device,
        notifier=notifier,
        workflow_factory=workflow_factory,
    )
    for workflow_id in TIKTOK_INBOX_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _run_new_followers(workflow: Any, payload: Mapping[str, Any], mode: str) -> dict[str, Any]:
    if mode == "follow_back":
        # `follow_back` matches the row by CONTAINMENT on the displayed name, which carries no
        # "@". The front scrapes its names off that same screen, but a plan or a CLI operator
        # writes "@name" -- and the containment would then never match, reporting a clean
        # failure for every recipient. Normalise here, at the free-form boundary.
        usernames = [name.lstrip("@") for name in list_param(payload, "usernames", "targetUsernames")]
        if not usernames:
            raise ValueError("TikTok follow-back requires at least one username")
        results = workflow.follow_back_users(usernames)
        return {
            "success": True,
            "mode": mode,
            "results": results,
            "followed_count": sum(1 for result in results if result.get("success")),
        }

    followers = workflow.read_new_followers(max_items=int_param(payload, "max_items", "maxItems", default=50))
    return {"success": True, "mode": "scrape", "followers": followers, "count": len(followers)}


def _run_unreplied(workflow: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    conversations = workflow.read_unreplied_conversations(
        max_items=int_param(payload, "max_items", "maxItems", default=30),
        only_unreplied=bool_param(payload, "only_unreplied", "onlyUnreplied", default=True),
    )
    return {
        "success": True,
        "conversations": conversations,
        "count": len(conversations),
        "unreplied_count": sum(1 for conv in conversations if conv.get("unreplied")),
    }


def _run_message_requests(workflow: Any, payload: Mapping[str, Any], mode: str) -> dict[str, Any]:
    if mode == "execute":
        decisions = _decisions_payload(payload)
        results = workflow.process_message_requests(decisions)
        return {
            "success": True,
            "mode": mode,
            "results": results,
            "processed_count": sum(1 for result in results if result.get("success")),
        }

    requests = workflow.read_message_requests(max_items=int_param(payload, "max_items", "maxItems", default=30))
    return {"success": True, "mode": "scrape", "requests": requests, "count": len(requests)}


def _run_activity(workflow: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    notifications = workflow.read_notifications(
        max_items=int_param(payload, "max_items", "maxItems", default=20)
    )
    return {"success": True, "notifications": notifications, "count": len(notifications)}


def _inbox_config(workflow_id: str, payload: Mapping[str, Any]) -> DMConfig:
    """Build the config each bridge runner builds for its own workflow.

    Only the two acting workflows carry a delay; the read-only ones run on plain defaults, exactly
    as `unreplied.py` and `activity.py` do.
    """
    if workflow_id in {TIKTOK_NEW_FOLLOWERS_WORKFLOW_ID, TIKTOK_DM_REQUESTS_WORKFLOW_ID}:
        return DMConfig(
            delay_between_conversations=float_param(
                payload, "delay_between_actions", "delayBetweenActions", default=1.0
            )
        )
    return DMConfig()


def _decisions_payload(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    raw_decisions = value_param(payload, "decisions", default=[])
    if not isinstance(raw_decisions, (list, tuple)):
        raise ValueError("TikTok message requests require decisions to be a list")

    decisions: list[dict[str, str]] = []
    for item in raw_decisions:
        if not isinstance(item, Mapping):
            continue
        username = str(item.get("username", "")).strip().lstrip("@")
        action = str(item.get("action", "")).strip().lower()
        if not username or action not in {"accept", "decline"}:
            continue
        decision = {"username": username, "action": action}
        message = str(item.get("message", "")).strip()
        if message:
            decision["message"] = message
        decisions.append(decision)

    if not decisions:
        raise ValueError("TikTok message requests require at least one accept/decline decision")
    return decisions


def _attach_callbacks(workflow: Any, notifier: Any) -> None:
    """Forward the same six callbacks the bridge wires to stdout, to an injected notifier."""
    if notifier is None:
        return

    forwarded = (
        ("set_on_new_follower_callback", "new_follower", "follower"),
        ("set_on_follow_back_result_callback", "follow_back_result", "result"),
        ("set_on_unreplied_callback", "unreplied_conversation", "conversation"),
        ("set_on_message_request_callback", "message_request", "request"),
        ("set_on_request_result_callback", "request_result", "result"),
        ("set_on_notification_callback", "activity_notification", "notification"),
    )
    for setter_name, event_type, argument in forwarded:
        setter = getattr(workflow, setter_name, None)
        if not callable(setter):
            continue
        setter(
            lambda item, event_type=event_type, argument=argument: notify(
                notifier, event_type, **{argument: item}
            )
        )
