"""The one launcher of a TikTok DM read and of a DM send, and their Agent handlers.

`run_tiktok_dm_read` and `run_tiktok_dm_send` are what the desktop bridges call and what the
handlers registered as `tiktok.automation.dm_read` and `.dm_send` (the CLI) call: start, drive
`DMWorkflow`, then record what was read or sent under the account read on the phone
(`taktik/core/database/tiktok_dm.py`). What differs between hosts is injected:
- `tiktok_startup() -> TikTokStartup`: clean restart, language, account; supplies the device and
  the account the conversations are recorded under.
- `notifier`: where the live events and statuses go (the bridge's stdout IPC; the log otherwise).
- `workflow_hook(workflow)`: registers the workflow for a stop signal.
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.

The cold-DM outreach handler lives here too; it is not on this path yet.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from loguru import logger

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    int_param,
    list_param,
    merge_invocation_payload,
    notify,
    value_param,
)
from taktik.core.social_media.tiktok.actions.business.workflows.dm.outreach import (
    TikTokDMOutreachWorkflow,
)
from taktik.core.social_media.tiktok.actions.business.workflows.dm.payload import (
    dm_messages_from_payload,
    dm_read_config_from_payload,
    dm_send_config_from_payload,
)


TIKTOK_DM_READ_WORKFLOW_ID = "tiktok.automation.dm_read"
TIKTOK_DM_SEND_WORKFLOW_ID = "tiktok.automation.dm_send"
TIKTOK_DM_OUTREACH_WORKFLOW_ID = "tiktok.standalone.tiktok_dm_outreach"
TIKTOK_DM_WORKFLOW_IDS = (TIKTOK_DM_READ_WORKFLOW_ID, TIKTOK_DM_SEND_WORKFLOW_ID)
DMWorkflowFactory = Callable[..., Any]
DMOutreachWorkflowFactory = Callable[..., Any]
StartupProvider = Callable[[], Any]
WorkflowHook = Callable[[Any], None]


def _default_workflow_factory() -> DMWorkflowFactory:
    # Resolved at call time, so the module's class is the one a run gets.
    from taktik.core.social_media.tiktok.actions.business.workflows.dm import workflow

    return workflow.DMWorkflow


def _emit(notifier: Any, method: str, *args: Any, **kwargs: Any) -> None:
    target = getattr(notifier, method, None)
    if callable(target):
        target(*args, **kwargs)


def _start(device, tiktok_startup: Optional[StartupProvider]) -> tuple[Any, Optional[str]]:
    """The device and the account read on the phone; without a startup, the given device and no
    account, so nothing is recorded."""
    if tiktok_startup is None:
        return device, None
    started = tiktok_startup()
    return started.device, started.bot_username


def _hook(workflow: Any, workflow_hook: Optional[WorkflowHook], notifier: Any) -> None:
    if workflow_hook is not None:
        workflow_hook(workflow)
    _attach_callbacks(workflow, notifier)


def run_tiktok_dm_read(
    payload: Any,
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[DMWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    workflow_hook: Optional[WorkflowHook] = None,
) -> dict[str, Any]:
    """Start, read the inbox, record the conversations read."""
    from taktik.core.database.tiktok_dm import record_conversations, resolve_account_id
    from taktik.core.social_media.tiktok.workflows.runtime.notifier import LoggingWorkflowNotifier

    notifier = notifier if notifier is not None else LoggingWorkflowNotifier()
    run_device, bot_username = _start(device, tiktok_startup)

    config = dm_read_config_from_payload(payload)
    logger.info("📥 Creating DM workflow...")
    _emit(notifier, "status", "running", "Reading DM conversations")
    workflow = (workflow_factory or _default_workflow_factory())(run_device, config)
    _hook(workflow, workflow_hook, notifier)

    logger.info("▶️ Reading conversations...")
    conversations = [_conversation_payload(conversation) for conversation in workflow.read_conversations()]

    # Persistence is best-effort and comes AFTER the read: a database problem must not cost
    # the conversations that were just read off the screen.
    record_conversations(resolve_account_id(bot_username), conversations)

    stats = workflow.get_stats().to_dict()
    notify(notifier, "dm_stats", stats=stats)
    logger.success(f"✅ DM reading completed: {len(conversations)} conversations")
    _emit(notifier, "status", "completed", f"Read {len(conversations)} conversations")
    return {"success": True, "conversations": conversations, "stats": stats}


def run_tiktok_dm_send(
    payload: Any,
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[DMWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    workflow_hook: Optional[WorkflowHook] = None,
) -> dict[str, Any]:
    """Start, send each message to its conversation, record the ones that left.

    Without a message, refused before the phone is touched.
    """
    from taktik.core.database.tiktok_dm import record_sent_results, resolve_account_id
    from taktik.core.social_media.tiktok.workflows.runtime.notifier import LoggingWorkflowNotifier

    messages = dm_messages_from_payload(payload)
    if not messages:
        raise ValueError("TikTok DM send requires at least one message")

    notifier = notifier if notifier is not None else LoggingWorkflowNotifier()
    run_device, bot_username = _start(device, tiktok_startup)

    workflow = (workflow_factory or _default_workflow_factory())(run_device, dm_send_config_from_payload(payload))
    _hook(workflow, workflow_hook, notifier)

    logger.info(f"▶️ Sending {len(messages)} messages...")
    _emit(notifier, "status", "running", f"Sending {len(messages)} messages")
    results = workflow.send_bulk_messages(messages)
    sent_count = sum(1 for result in results if result.get("success"))

    # What we sent is the CERTAIN half of the direction question: the reader cannot see who wrote
    # a bubble, so a later read recognises our own messages only from these rows.
    record_sent_results(resolve_account_id(bot_username), messages, results)

    stats = workflow.get_stats().to_dict()
    notify(notifier, "dm_stats", stats=stats)
    logger.success(f"✅ DM sending completed: {sent_count}/{len(messages)} sent")
    _emit(notifier, "status", "completed", f"Sent {sent_count}/{len(messages)} messages")
    return {"success": True, "results": results, "sent_count": sent_count, "stats": stats}


def build_tiktok_dm_handler(
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[DMWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
) -> WorkflowHandler:
    """Build the DM read/send handler; the id names the direction."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        if invocation.workflow_id == TIKTOK_DM_READ_WORKFLOW_ID:
            run = run_tiktok_dm_read
        elif invocation.workflow_id == TIKTOK_DM_SEND_WORKFLOW_ID:
            run = run_tiktok_dm_send
        else:
            raise ValueError(f"Unsupported TikTok DM workflow id: {invocation.workflow_id}")
        return run(
            merge_invocation_payload(invocation, payload),
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
        )

    return handler


def register_tiktok_dm_handlers(
    registry: WorkflowRegistry,
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[DMWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
) -> WorkflowRegistry:
    """Register the TikTok DM read and send handlers into an injected Agent registry."""
    handler = build_tiktok_dm_handler(
        device=device,
        notifier=notifier,
        workflow_factory=workflow_factory,
        tiktok_startup=tiktok_startup,
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
    """Forward the DM callbacks of the workflow to the notifier, as stdout events on the desktop."""
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


__all__ = [
    "TIKTOK_DM_OUTREACH_WORKFLOW_ID",
    "TIKTOK_DM_READ_WORKFLOW_ID",
    "TIKTOK_DM_SEND_WORKFLOW_ID",
    "TIKTOK_DM_WORKFLOW_IDS",
    "build_tiktok_dm_handler",
    "build_tiktok_dm_outreach_handler",
    "register_tiktok_dm_handlers",
    "register_tiktok_dm_outreach_handlers",
    "run_tiktok_dm_read",
    "run_tiktok_dm_send",
]
