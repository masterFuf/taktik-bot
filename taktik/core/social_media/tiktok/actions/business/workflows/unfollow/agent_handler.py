"""The one launcher of a TikTok unfollow run, and its Agent handler.

`run_tiktok_unfollow` is what the desktop bridge calls and what the handler registered as
`tiktok.standalone.tiktok_unfollow` (the CLI) calls: start TikTok, read the acting account on the
phone, unfollow. The acting account is what lets the workflow date a follow (the minimum age) and
write a confirmed unfollow; without the start, the CLI ran with none. What differs between hosts is
injected:
- `tiktok_startup() -> TikTokStartup`: clean restart, language, account; supplies the device and
  the acting account. Without it the injected `device` is used as is, with no account.
- `notifier`: where the live events and statuses go (the bridge's stdout IPC; the log otherwise).
- `workflow_hook(workflow)`: registers the workflow for a stop signal.
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from loguru import logger

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    merge_invocation_payload,
    notify,
)
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.models import NOT_CONFIRMED
from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.payload import (
    unfollow_config_from_payload,
)


TIKTOK_UNFOLLOW_WORKFLOW_ID = "tiktok.standalone.tiktok_unfollow"
UnfollowWorkflowFactory = Callable[..., Any]
StartupProvider = Callable[[], Any]
WorkflowHook = Callable[[Any], None]


def _default_workflow_factory() -> UnfollowWorkflowFactory:
    # Resolved at call time, so the module's class is the one a run gets.
    from taktik.core.social_media.tiktok.actions.business.workflows.unfollow import workflow

    return workflow.UnfollowWorkflow


def _emit(notifier: Any, method: str, *args: Any, **kwargs: Any) -> None:
    target = getattr(notifier, method, None)
    if callable(target):
        target(*args, **kwargs)


def run_tiktok_unfollow(
    payload: Mapping[str, Any],
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[UnfollowWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    workflow_hook: Optional[WorkflowHook] = None,
) -> dict[str, Any]:
    """Start, then unfollow as the account read on the phone (or the one the payload names)."""
    from taktik.core.social_media.tiktok.workflows.runtime.notifier import LoggingWorkflowNotifier

    notifier = notifier if notifier is not None else LoggingWorkflowNotifier()
    config = unfollow_config_from_payload(payload)
    max_unfollows = config.max_unfollows

    run_device = device
    if tiktok_startup is not None:
        started = tiktok_startup()
        run_device = started.device
        # The acting account dates its follows and files its unfollows; the startup reads its handle.
        config.bot_username = config.bot_username or started.bot_username

    logger.info(f"⏱️ Pause between unfollows: {config.min_delay:g}-{config.max_delay:g} s")
    if config.min_follow_age_days:
        logger.info(
            f"🕒 Keeping accounts followed less than {config.min_follow_age_days} day(s) ago, "
            "and accounts whose follow date is unknown"
        )

    workflow = (workflow_factory or _default_workflow_factory())(run_device, config)
    if workflow_hook is not None:
        workflow_hook(workflow)
    _attach_callbacks(workflow, notifier, target=max_unfollows)

    _emit(notifier, "status", "running", f"Unfollowing users (0/{max_unfollows})")
    stats = workflow.run()

    notify(notifier, "unfollow_stats", stats={**stats.to_dict(), "target": max_unfollows})
    logger.success(
        f"✅ Unfollow workflow completed: {stats.unfollowed} users unfollowed (confirmed), "
        f"{stats.unconfirmed} tap(s) not confirmed, kept: {stats.refusals or 'none'}"
        + (f", stopped: {stats.stop_reason}" if stats.stop_reason else "")
    )
    done = f"Unfollowed {stats.unfollowed} users"
    if stats.stop_reason and callable(getattr(notifier, "send", None)):
        # The run says why it stopped (`action_blocked`, `unfollow_unconfirmed`), as the others.
        _emit(notifier, "send", "status", status="completed", message=done,
              completion_reason=stats.stop_reason)
    else:
        _emit(notifier, "status", "completed", done)
    return {"success": True, "stats": stats.to_dict()}


def build_tiktok_unfollow_handler(
    *,
    device,
    notifier=None,
    workflow_factory: Optional[UnfollowWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
) -> WorkflowHandler:
    """Build an injectable unfollow handler for the Agent runtime."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        return run_tiktok_unfollow(
            merge_invocation_payload(invocation, payload),
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
        )

    return handler


def register_tiktok_unfollow_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    notifier=None,
    workflow_factory: Optional[UnfollowWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
) -> WorkflowRegistry:
    """Register TikTok unfollow handlers into an injected Agent registry."""
    registry.register(
        TIKTOK_UNFOLLOW_WORKFLOW_ID,
        build_tiktok_unfollow_handler(
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
        ),
    )
    return registry


def _attach_callbacks(workflow: Any, notifier: Any, *, target: int) -> None:
    """Forward the unfollow callbacks of the workflow to the notifier, as stdout events on the desktop."""
    if notifier is None:
        return

    if hasattr(workflow, "set_on_unfollow_callback"):
        workflow.set_on_unfollow_callback(
            lambda username, count: notify(
                notifier,
                "unfollow_event",
                event="unfollowed",
                username=username,
                count=count,
            )
        )
    if hasattr(workflow, "set_on_skip_callback"):
        workflow.set_on_skip_callback(
            lambda username, reason="friends": notify(
                notifier,
                "unfollow_event",
                event="skipped",
                reason=reason,
                username=username,
            )
        )
    if hasattr(workflow, "set_on_unconfirmed_callback"):
        # A tap the row did not confirm: not an unfollow, and said so.
        workflow.set_on_unconfirmed_callback(
            lambda username, state: notify(
                notifier,
                "unfollow_event",
                event=NOT_CONFIRMED,
                reason=NOT_CONFIRMED,
                state=state,
                username=username,
            )
        )
    if hasattr(workflow, "set_on_stats_callback"):
        workflow.set_on_stats_callback(
            lambda stats: notify(notifier, "unfollow_stats", stats={**stats, "target": target})
        )


__all__ = [
    "TIKTOK_UNFOLLOW_WORKFLOW_ID",
    "build_tiktok_unfollow_handler",
    "register_tiktok_unfollow_handlers",
    "run_tiktok_unfollow",
]
