"""The one launcher of a TikTok follow-graph sync, and its Agent handlers.

`run_tiktok_sync_lists` is what the desktop bridge calls and what the handlers registered as
`tiktok.automation.sync_following`, `.sync_followers` and `.sync_lists` (the CLI) call: read the
acting account's own list(s) and record them. What differs between hosts is injected:
- `tiktok_startup() -> TikTokStartup`: clean restart, language, account; supplies the device and
  the account the graph is recorded under.
- `workflow_hook(workflow, list_type, bot_username)`: wires the live events; defaults to
  `notifier`.
- `on_finished(stats, list_type)`: reports the end of the run.
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
from taktik.core.social_media.tiktok.actions.business.workflows.followers.payload import (
    bot_username_from_payload,
)
from taktik.core.social_media.tiktok.actions.business.workflows.sync_lists.payload import (
    list_type_from_payload,
    sync_config_from_payload,
)


TIKTOK_SYNC_FOLLOWING_WORKFLOW_ID = "tiktok.automation.sync_following"
TIKTOK_SYNC_FOLLOWERS_WORKFLOW_ID = "tiktok.automation.sync_followers"
TIKTOK_SYNC_LISTS_WORKFLOW_ID = "tiktok.automation.sync_lists"
TIKTOK_SYNC_WORKFLOW_IDS = (
    TIKTOK_SYNC_FOLLOWING_WORKFLOW_ID,
    TIKTOK_SYNC_FOLLOWERS_WORKFLOW_ID,
    TIKTOK_SYNC_LISTS_WORKFLOW_ID,
)
SyncListsWorkflowFactory = Callable[..., Any]
StartupProvider = Callable[[], Any]
WorkflowHook = Callable[[Any, str, str], None]
FinishedHook = Callable[[Any, str], None]


class SyncAccountUnknownError(RuntimeError):
    """The acting account could not be read, so the graph would have no owner."""


def _default_workflow_factory() -> SyncListsWorkflowFactory:
    # Resolved at call time, so the module's class is the one a run gets.
    from taktik.core.social_media.tiktok.actions.business.workflows.sync_lists import workflow

    return workflow.SyncListsWorkflow


def _attach_row_callback(workflow: Any, notifier: Any) -> None:
    if notifier is None:
        return
    workflow.set_on_row_callback(
        lambda row: notify(
            notifier,
            "sync_user_discovered",
            list_type=row.get("list_type"),
            username=row.get("username"),
            display_name=row.get("display_name"),
            relationship=row.get("relationship"),
            is_new=row.get("is_new"),
        )
    )


def run_tiktok_sync_lists(
    payload: Any,
    *,
    workflow_type: Optional[str] = None,
    device=None,
    notifier=None,
    workflow_factory: Optional[SyncListsWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    workflow_hook: Optional[WorkflowHook] = None,
    on_finished: Optional[FinishedHook] = None,
) -> dict[str, Any]:
    """Start, then read and record the list(s) a payload names. Success means no error on the way."""
    list_type = list_type_from_payload(payload, workflow_type)

    run_device = device
    bot_username = bot_username_from_payload(payload)
    if tiktok_startup is not None:
        started = tiktok_startup()
        run_device = started.device
        bot_username = started.bot_username or bot_username
    if not bot_username:
        # A graph written under a guessed account is worse than none.
        logger.error("No bot username: refusing to write a follow graph with no owner")
        raise SyncAccountUnknownError("Could not identify the acting TikTok account")

    config = sync_config_from_payload(payload, list_type)
    workflow = (workflow_factory or _default_workflow_factory())(run_device, config)
    if workflow_hook is not None:
        workflow_hook(workflow, list_type, bot_username)
    else:
        _attach_row_callback(workflow, notifier)

    stats = workflow.run(bot_username=bot_username)
    if on_finished is not None:
        on_finished(stats, list_type)
    return {"success": stats.errors == 0, "list_type": list_type, "stats": stats.to_dict()}


def build_tiktok_sync_lists_handler(
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[SyncListsWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
) -> WorkflowHandler:
    """Build the follow-graph sync handler; the id names the list(s)."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        return run_tiktok_sync_lists(
            merge_invocation_payload(invocation, payload),
            workflow_type=invocation.workflow_id.rsplit(".", 1)[-1],
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
        )

    return handler


def register_tiktok_sync_lists_handlers(
    registry: WorkflowRegistry,
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[SyncListsWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
) -> WorkflowRegistry:
    """Register the three TikTok follow-graph sync handlers into an injected registry."""
    handler = build_tiktok_sync_lists_handler(
        device=device,
        notifier=notifier,
        workflow_factory=workflow_factory,
        tiktok_startup=tiktok_startup,
    )
    for workflow_id in TIKTOK_SYNC_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


__all__ = [
    "SyncAccountUnknownError",
    "TIKTOK_SYNC_FOLLOWERS_WORKFLOW_ID",
    "TIKTOK_SYNC_FOLLOWING_WORKFLOW_ID",
    "TIKTOK_SYNC_LISTS_WORKFLOW_ID",
    "TIKTOK_SYNC_WORKFLOW_IDS",
    "build_tiktok_sync_lists_handler",
    "register_tiktok_sync_lists_handlers",
    "run_tiktok_sync_lists",
]
