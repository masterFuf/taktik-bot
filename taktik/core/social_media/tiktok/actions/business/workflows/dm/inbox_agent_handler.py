"""The one launcher of the TikTok inbox flows, and their Agent handlers.

`run_tiktok_inbox` is what the four desktop bridges call and what the handlers registered as
`tiktok.automation.new_followers`, `.dm_unreplied`, `.dm_requests` and `.dm_activity` (the CLI)
call. Each flow drives `DMWorkflow`: new followers (list, or follow back the given names; after a
list, the AI welcome pass when the payload asks for it), unreplied conversations, message requests
(list, or accept/decline) and activity. What differs between hosts is injected:
- `tiktok_startup() -> TikTokStartup`: clean restart, language, account; supplies the device, the
  account the welcome pass records under, and the manager its DM reuses.
- `notifier`: where the live events and statuses go (the bridge's stdout IPC; the log otherwise).
- `workflow_hook(workflow)`: registers each workflow for a stop signal.
- `tiktok_welcome_qualifier(ai_config, language)`: the welcome pass's AI verdicts.
- `send_welcome_dms`: whether this host sends the welcome DM the pass decided on (the desktop
  does; the CLI does not, pending a product decision).
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from loguru import logger

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    merge_invocation_payload,
    notify,
)
from taktik.core.social_media.tiktok.actions.business.workflows.dm.inbox_payload import (
    ACTIVITY,
    EXECUTE,
    FOLLOW_BACK,
    NEW_FOLLOWERS,
    REQUESTS,
    UNREPLIED,
    device_id_from_payload,
    follow_back_usernames_from_payload,
    inbox_config_from_payload,
    inbox_mode_from_payload,
    max_items_from_payload,
    only_unreplied_from_payload,
    request_decisions_from_payload,
)


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
#: Workflow id -> the flow (the bridge's `workflowType`).
INBOX_FLOW_BY_WORKFLOW_ID = {
    TIKTOK_NEW_FOLLOWERS_WORKFLOW_ID: NEW_FOLLOWERS,
    TIKTOK_DM_UNREPLIED_WORKFLOW_ID: UNREPLIED,
    TIKTOK_DM_REQUESTS_WORKFLOW_ID: REQUESTS,
    TIKTOK_DM_ACTIVITY_WORKFLOW_ID: ACTIVITY,
}
DMWorkflowFactory = Callable[..., Any]
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


def _start(device, tiktok_startup: Optional[StartupProvider]):
    from taktik.core.social_media.tiktok.workflows.runtime.startup import TikTokStartup

    if tiktok_startup is not None:
        return tiktok_startup()
    return TikTokStartup(device=device, bot_username=None)


def run_tiktok_inbox(
    payload: Any,
    *,
    flow: str,
    device=None,
    notifier=None,
    workflow_factory: Optional[DMWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    workflow_hook: Optional[WorkflowHook] = None,
    tiktok_welcome_qualifier=None,
    outreach_notifier=None,
    send_welcome_dms: bool = False,
) -> dict[str, Any]:
    """Start, then run one inbox flow from a payload. A request with nothing to act on is refused
    before the phone is touched."""
    from taktik.core.social_media.tiktok.workflows.runtime.notifier import LoggingWorkflowNotifier

    if flow not in INBOX_FLOW_BY_WORKFLOW_ID.values():
        raise ValueError(f"Unsupported TikTok inbox flow: {flow}")
    notifier = notifier if notifier is not None else LoggingWorkflowNotifier()
    mode = inbox_mode_from_payload(payload)

    usernames = decisions = None
    if flow == NEW_FOLLOWERS and mode == FOLLOW_BACK:
        usernames = follow_back_usernames_from_payload(payload)
        if not usernames:
            raise ValueError("TikTok follow-back requires at least one username")
    if flow == REQUESTS and mode == EXECUTE:
        decisions = request_decisions_from_payload(payload)
        if not decisions:
            raise ValueError("TikTok message requests require at least one accept/decline decision")

    started = _start(device, tiktok_startup)
    workflow = (workflow_factory or _default_workflow_factory())(started.device, inbox_config_from_payload(flow, payload))
    if workflow_hook is not None:
        workflow_hook(workflow)
    _attach_callbacks(workflow, notifier)

    if flow == NEW_FOLLOWERS and usernames is not None:
        return _follow_back(workflow, usernames, notifier)
    if flow == NEW_FOLLOWERS:
        return _read_new_followers(
            workflow, payload, started, notifier,
            workflow_hook=workflow_hook, qualifier_factory=tiktok_welcome_qualifier,
            outreach_notifier=outreach_notifier, send_welcome_dms=send_welcome_dms,
        )
    if flow == UNREPLIED:
        return _read_unreplied(workflow, payload, notifier)
    if flow == REQUESTS and decisions is not None:
        return _process_requests(workflow, decisions, notifier)
    if flow == REQUESTS:
        return _read_requests(workflow, payload, notifier)
    return _read_activity(workflow, payload, notifier)


def _follow_back(workflow, usernames: list[str], notifier) -> dict[str, Any]:
    logger.info(f"➕ Follow-back de {len(usernames)} follower(s)")
    _emit(notifier, "status", "running", f"Following back {len(usernames)} follower(s)")
    results = workflow.follow_back_users(usernames)
    done = sum(1 for result in results if result.get("success"))
    logger.success(f"✅ Follow-back terminé : {done}/{len(usernames)}")
    _emit(notifier, "status", "completed", f"Followed back {done}/{len(usernames)}")
    return {"success": True, "mode": FOLLOW_BACK, "results": results, "followed_count": done}


def _read_new_followers(workflow, payload, started, notifier, *, workflow_hook, qualifier_factory,
                        outreach_notifier, send_welcome_dms) -> dict[str, Any]:
    from taktik.core.social_media.tiktok.services.welcome import parse_welcome_policy
    from taktik.core.social_media.tiktok.workflows.core.ai_hooks import (
        ai_config_from_payload,
        app_language_from_payload,
    )

    max_items = max_items_from_payload(NEW_FOLLOWERS, payload)
    logger.info(f"👥 Scrape des nouveaux followers (max {max_items})")
    _emit(notifier, "status", "running", "Reading new followers")
    followers = workflow.read_new_followers(max_items=max_items)
    logger.success(f"✅ {len(followers)} nouveaux followers listés")

    result: dict[str, Any] = {"success": True, "mode": "scrape", "followers": followers, "count": len(followers)}
    # The AI pass runs only when the payload asked for it, by name. Reading the list is what
    # this mode promises; anything beyond that has to be requested.
    ai_config = ai_config_from_payload(payload)
    policy = parse_welcome_policy(ai_config)
    if policy.enabled and followers:
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.welcome_pass import run_welcome_pass

        result["welcome"] = run_welcome_pass(
            followers, policy, workflow=workflow, started=started, device_id=device_id_from_payload(payload),
            ai_config=ai_config, language=app_language_from_payload(payload), notifier=notifier,
            qualifier_factory=qualifier_factory, outreach_notifier=outreach_notifier,
            workflow_hook=workflow_hook, send_welcome_dms=send_welcome_dms,
        )

    _emit(notifier, "status", "completed", f"Listed {len(followers)} new followers")
    return result


def _read_unreplied(workflow, payload, notifier) -> dict[str, Any]:
    conversations = workflow.read_unreplied_conversations(
        max_items=max_items_from_payload(UNREPLIED, payload),
        only_unreplied=only_unreplied_from_payload(payload),
    )
    unreplied = sum(1 for conversation in conversations if conversation.get("unreplied"))
    logger.success(f"✅ {len(conversations)} conversation(s), {unreplied} non-répondue(s)")
    _emit(notifier, "status", "completed", f"{unreplied} unreplied / {len(conversations)} conversations")
    return {"success": True, "conversations": conversations, "count": len(conversations),
            "unreplied_count": unreplied}


def _process_requests(workflow, decisions: list[dict[str, str]], notifier) -> dict[str, Any]:
    logger.info(f"📥 Traitement de {len(decisions)} demande(s)")
    _emit(notifier, "status", "running", f"Processing {len(decisions)} request(s)")
    results = workflow.process_message_requests(decisions)
    done = sum(1 for result in results if result.get("success"))
    logger.success(f"✅ Demandes traitées : {done}/{len(decisions)}")
    _emit(notifier, "status", "completed", f"Processed {done}/{len(decisions)} requests")
    return {"success": True, "mode": EXECUTE, "results": results, "processed_count": done}


def _read_requests(workflow, payload, notifier) -> dict[str, Any]:
    max_items = max_items_from_payload(REQUESTS, payload)
    logger.info(f"📥 Scrape des demandes de messages (max {max_items})")
    _emit(notifier, "status", "running", "Reading message requests")
    requests = workflow.read_message_requests(max_items=max_items)
    logger.success(f"✅ {len(requests)} demande(s) listée(s)")
    _emit(notifier, "status", "completed", f"Listed {len(requests)} message requests")
    return {"success": True, "mode": "scrape", "requests": requests, "count": len(requests)}


def _read_activity(workflow, payload, notifier) -> dict[str, Any]:
    notifications = workflow.read_notifications(max_items=max_items_from_payload(ACTIVITY, payload))
    logger.success(f"✅ {len(notifications)} notification(s) lue(s)")
    _emit(notifier, "status", "completed", f"Read {len(notifications)} notifications")
    return {"success": True, "notifications": notifications, "count": len(notifications)}


def build_tiktok_inbox_handler(
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[DMWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_welcome_qualifier=None,
    send_welcome_dms: bool = False,
) -> WorkflowHandler:
    """Build the handler of the four inbox ids; the id names the flow."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        flow = INBOX_FLOW_BY_WORKFLOW_ID.get(invocation.workflow_id)
        if flow is None:
            raise ValueError(f"Unsupported TikTok inbox workflow id: {invocation.workflow_id}")
        return run_tiktok_inbox(
            merge_invocation_payload(invocation, payload),
            flow=flow,
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
            tiktok_welcome_qualifier=tiktok_welcome_qualifier,
            send_welcome_dms=send_welcome_dms,
        )

    return handler


def register_tiktok_inbox_handlers(
    registry: WorkflowRegistry,
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[DMWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_welcome_qualifier=None,
    send_welcome_dms: bool = False,
) -> WorkflowRegistry:
    """Register the four TikTok inbox handlers into an injected Agent registry."""
    handler = build_tiktok_inbox_handler(
        device=device,
        notifier=notifier,
        workflow_factory=workflow_factory,
        tiktok_startup=tiktok_startup,
        tiktok_welcome_qualifier=tiktok_welcome_qualifier,
        send_welcome_dms=send_welcome_dms,
    )
    for workflow_id in TIKTOK_INBOX_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _attach_callbacks(workflow: Any, notifier: Any) -> None:
    """Forward the six inbox callbacks of the workflow to the notifier, as stdout events on the
    desktop."""
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


__all__ = [
    "INBOX_FLOW_BY_WORKFLOW_ID",
    "TIKTOK_DM_ACTIVITY_WORKFLOW_ID",
    "TIKTOK_DM_REQUESTS_WORKFLOW_ID",
    "TIKTOK_DM_UNREPLIED_WORKFLOW_ID",
    "TIKTOK_INBOX_WORKFLOW_IDS",
    "TIKTOK_NEW_FOLLOWERS_WORKFLOW_ID",
    "build_tiktok_inbox_handler",
    "register_tiktok_inbox_handlers",
    "run_tiktok_inbox",
]
