"""Agent runtime handlers for TikTok DM workflows."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    bool_param,
    float_param,
    int_param,
    merge_invocation_payload,
    notify,
    value_param,
)
from taktik.core.social_media.tiktok.actions.business.workflows.dm.models import DMConfig
from taktik.core.social_media.tiktok.actions.business.workflows.dm.workflow import DMWorkflow


TIKTOK_DM_READ_WORKFLOW_ID = "tiktok.automation.dm_read"
TIKTOK_DM_SEND_WORKFLOW_ID = "tiktok.automation.dm_send"
TIKTOK_DM_WORKFLOW_IDS = (TIKTOK_DM_READ_WORKFLOW_ID, TIKTOK_DM_SEND_WORKFLOW_ID)
DMWorkflowFactory = Callable[..., Any]


def build_tiktok_dm_handler(
    *,
    device,
    notifier=None,
    workflow_factory: DMWorkflowFactory = DMWorkflow,
) -> WorkflowHandler:
    """Build an injectable DM handler without owning bridge startup."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = merge_invocation_payload(invocation, payload)

        if invocation.workflow_id == TIKTOK_DM_READ_WORKFLOW_ID:
            workflow = workflow_factory(device, _dm_config(invocation.workflow_id, merged))
            _attach_callbacks(workflow, notifier)
            conversations = workflow.read_conversations()
            return {
                "success": True,
                "conversations": [_conversation_payload(conv) for conv in conversations],
                "stats": workflow.get_stats().to_dict(),
            }

        if invocation.workflow_id == TIKTOK_DM_SEND_WORKFLOW_ID:
            messages = _messages_payload(merged)
            workflow = workflow_factory(device, _dm_config(invocation.workflow_id, merged))
            _attach_callbacks(workflow, notifier)
            results = workflow.send_bulk_messages(messages)
            sent_count = sum(1 for result in results if result.get("success"))
            return {
                "success": True,
                "results": results,
                "sent_count": sent_count,
                "stats": workflow.get_stats().to_dict(),
            }

        raise ValueError(f"Unsupported TikTok DM workflow id: {invocation.workflow_id}")

    return handler


def register_tiktok_dm_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    notifier=None,
    workflow_factory: DMWorkflowFactory = DMWorkflow,
) -> WorkflowRegistry:
    """Register TikTok DM handlers into an injected Agent registry."""
    handler = build_tiktok_dm_handler(
        device=device,
        notifier=notifier,
        workflow_factory=workflow_factory,
    )
    for workflow_id in TIKTOK_DM_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _dm_config(workflow_id: str, payload: Mapping[str, Any]) -> DMConfig:
    if workflow_id == TIKTOK_DM_READ_WORKFLOW_ID:
        return DMConfig(
            max_conversations=int_param(payload, "max_conversations", "maxConversations", default=20),
            skip_notifications=bool_param(
                payload, "skip_notifications", "skipNotifications", default=True
            ),
            skip_groups=bool_param(payload, "skip_groups", "skipGroups", default=False),
            only_unread=bool_param(payload, "only_unread", "onlyUnread", default=False),
            delay_between_conversations=float_param(
                payload, "delay_between_conversations", "delayBetweenConversations", default=1.0
            ),
            mark_as_read=bool_param(payload, "mark_as_read", "markAsRead", default=True),
            close_sticker_suggestions=bool_param(
                payload, "close_sticker_suggestions", "closeStickerSuggestions", default=True
            ),
        )

    if workflow_id == TIKTOK_DM_SEND_WORKFLOW_ID:
        return DMConfig(
            delay_between_conversations=float_param(
                payload, "delay_between_conversations", "delayBetweenMessages", default=1.0
            ),
            delay_after_send=float_param(payload, "delay_after_send", "delayAfterSend", default=0.5),
            close_sticker_suggestions=bool_param(
                payload, "close_sticker_suggestions", "closeStickerSuggestions", default=True
            ),
        )

    raise ValueError(f"Unsupported TikTok DM workflow id: {workflow_id}")


def _messages_payload(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    raw_messages = value_param(payload, "messages", default=[])
    if raw_messages:
        if not isinstance(raw_messages, list):
            raise ValueError("TikTok DM send requires messages to be a list")
        messages = [
            {
                "conversation": str(item.get("conversation", "")).strip(),
                "message": str(item.get("message", "")).strip(),
            }
            for item in raw_messages
            if isinstance(item, Mapping)
        ]
    else:
        conversation = str(value_param(payload, "conversation", "username", default="")).strip()
        message = str(value_param(payload, "message", default="")).strip()
        messages = [{"conversation": conversation, "message": message}] if conversation or message else []

    if not messages:
        raise ValueError("TikTok DM send requires at least one message")
    return messages


def _attach_callbacks(workflow: Any, notifier: Any) -> None:
    if notifier is None:
        return

    if hasattr(workflow, "set_on_conversation_callback"):
        workflow.set_on_conversation_callback(
            lambda conversation: notify(notifier, "dm_conversation", conversation=conversation)
        )
    if hasattr(workflow, "set_on_message_sent_callback"):
        workflow.set_on_message_sent_callback(
            lambda result: notify(
                notifier,
                "dm_sent",
                conversation=result.get("conversation", ""),
                success=result.get("success", False),
                error=result.get("error"),
            )
        )
    if hasattr(workflow, "set_on_stats_callback"):
        workflow.set_on_stats_callback(lambda stats: notify(notifier, "dm_stats", stats=stats))
    if hasattr(workflow, "set_on_progress_callback"):
        workflow.set_on_progress_callback(
            lambda current, total, name: notify(
                notifier, "dm_progress", current=current, total=total, name=name
            )
        )


def _conversation_payload(conversation: Any) -> dict[str, Any]:
    to_dict = getattr(conversation, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return dict(conversation)
