"""Agent runtime handlers for TikTok DM workflows."""

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
from taktik.core.social_media.tiktok.actions.business.workflows.dm.outreach import (
    TikTokDMOutreachWorkflow,
)
from taktik.core.social_media.tiktok.actions.business.workflows.dm.workflow import DMWorkflow


TIKTOK_DM_READ_WORKFLOW_ID = "tiktok.automation.dm_read"
TIKTOK_DM_SEND_WORKFLOW_ID = "tiktok.automation.dm_send"
TIKTOK_DM_OUTREACH_WORKFLOW_ID = "tiktok.standalone.tiktok_dm_outreach"
TIKTOK_DM_WORKFLOW_IDS = (TIKTOK_DM_READ_WORKFLOW_ID, TIKTOK_DM_SEND_WORKFLOW_ID)
DMWorkflowFactory = Callable[..., Any]
DMOutreachWorkflowFactory = Callable[..., Any]


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


def build_tiktok_dm_outreach_handler(
    *,
    device_id: str,
    notifier=None,
    duplicate_checker=None,
    sent_dm_recorder=None,
    workflow_factory: DMOutreachWorkflowFactory = TikTokDMOutreachWorkflow,
) -> WorkflowHandler:
    """Build an injectable cold-DM outreach handler for the Agent runtime."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = merge_invocation_payload(invocation, payload)
        params = _outreach_params(merged, default_session_id=device_id)
        workflow = workflow_factory(
            device_id,
            notifier=notifier,
            duplicate_checker=duplicate_checker,
            sent_dm_recorder=sent_dm_recorder,
        )
        if hasattr(workflow, "connect") and not workflow.connect():
            raise RuntimeError("TikTok DM outreach failed to connect to device")
        return workflow.run(**params)

    return handler


def register_tiktok_dm_outreach_handlers(
    registry: WorkflowRegistry,
    *,
    device_id: str,
    notifier=None,
    duplicate_checker=None,
    sent_dm_recorder=None,
    workflow_factory: DMOutreachWorkflowFactory = TikTokDMOutreachWorkflow,
) -> WorkflowRegistry:
    """Register TikTok cold-DM outreach handler into an injected Agent registry."""
    registry.register(
        TIKTOK_DM_OUTREACH_WORKFLOW_ID,
        build_tiktok_dm_outreach_handler(
            device_id=device_id,
            notifier=notifier,
            duplicate_checker=duplicate_checker,
            sent_dm_recorder=sent_dm_recorder,
            workflow_factory=workflow_factory,
        ),
    )
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


def _outreach_params(payload: Mapping[str, Any], *, default_session_id: str) -> dict[str, Any]:
    recipients = list_param(payload, "recipients", "targetUsernames", "target_usernames")
    messages = _outreach_messages(payload)
    if not recipients:
        raise ValueError("TikTok DM outreach requires at least one recipient")
    if not messages:
        raise ValueError("TikTok DM outreach requires at least one message")

    return {
        "recipients": recipients,
        "messages": messages,
        "delay_min": int_param(payload, "delay_min", "delayMin", default=30),
        "delay_max": int_param(payload, "delay_max", "delayMax", default=60),
        "max_dms": int_param(payload, "max_dms", "maxDms", default=50),
        "account_id": int_param(payload, "account_id", "accountId", default=1),
        "session_id": str(value_param(payload, "session_id", "sessionId", default=default_session_id)),
    }


def _outreach_messages(payload: Mapping[str, Any]) -> list[str]:
    raw_messages = value_param(payload, "messages", "messageTemplates", default=[])
    if isinstance(raw_messages, str):
        return [raw_messages.strip()] if raw_messages.strip() else []
    if isinstance(raw_messages, (list, tuple, set)):
        return [str(message).strip() for message in raw_messages if str(message).strip()]
    return []


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
