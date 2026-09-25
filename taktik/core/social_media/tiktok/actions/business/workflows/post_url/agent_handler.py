"""The one launcher of a TikTok Post URL run, and its Agent handler.

`run_tiktok_post_url` is what the desktop bridge calls and what the handler registered as
`tiktok.automation.post_url` (the CLI) calls: open one video by its link, read who commented,
visit them with the Followers interaction settings. What differs between hosts is injected:
- `tiktok_startup() -> TikTokStartup`: clean restart, language, account; supplies the device and
  the account the run acts as.
- `tiktok_ai_hooks(ai_config, language)`: installs the AI hooks the run asks for.
- `workflow_hook(workflow, post_url)`: wires the live events; defaults to `notifier`.
- `on_finished(stats)`: reports the end of the run.
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    attach_profile_callbacks,
    merge_invocation_payload,
)
from taktik.core.social_media.tiktok.actions.business.workflows.followers.payload import (
    bot_username_from_payload,
)
from taktik.core.social_media.tiktok.actions.business.workflows.post_url.payload import (
    device_id_from_payload,
    post_url_config_from_payload,
    post_url_from_payload,
)


TIKTOK_POST_URL_WORKFLOW_ID = "tiktok.automation.post_url"
PostUrlWorkflowFactory = Callable[..., Any]
StartupProvider = Callable[[], Any]
AIHooks = Callable[[Any, str], None]
WorkflowHook = Callable[[Any, str], None]
FinishedHook = Callable[[Any], None]


def _default_workflow_factory() -> PostUrlWorkflowFactory:
    # Resolved at call time, so the module's class is the one a run gets.
    from taktik.core.social_media.tiktok.actions.business.workflows.post_url import workflow

    return workflow.PostUrlWorkflow


def run_tiktok_post_url(
    payload: Any,
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[PostUrlWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
    workflow_hook: Optional[WorkflowHook] = None,
    on_finished: Optional[FinishedHook] = None,
) -> dict[str, Any]:
    """Start, hook, configure and run one Post URL pass from a payload."""
    from taktik.core.social_media.tiktok.workflows.core.ai_hooks import (
        ai_config_from_payload,
        app_language_from_payload,
    )

    post_url = post_url_from_payload(payload)
    if not post_url:
        raise ValueError("TikTok post URL requires a postUrl")

    run_device = device
    bot_username = bot_username_from_payload(payload)
    if tiktok_startup is not None:
        started = tiktok_startup()
        run_device = started.device
        bot_username = started.bot_username or bot_username

    if tiktok_ai_hooks is not None:
        tiktok_ai_hooks(ai_config_from_payload(payload), app_language_from_payload(payload))

    config = post_url_config_from_payload(payload)
    workflow = (workflow_factory or _default_workflow_factory())(
        run_device, config, device_id=device_id_from_payload(payload)
    )
    if workflow_hook is not None:
        workflow_hook(workflow, post_url)
    else:
        attach_profile_callbacks(workflow, notifier)

    stats = workflow.run(bot_username=bot_username)
    if on_finished is not None:
        on_finished(stats)
    return {"success": True, "post_url": post_url, "stats": stats.to_dict()}


def build_tiktok_post_url_handler(
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[PostUrlWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
) -> WorkflowHandler:
    """Build the Post URL handler for the Agent runtime."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        return run_tiktok_post_url(
            merge_invocation_payload(invocation, payload),
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
            tiktok_ai_hooks=tiktok_ai_hooks,
        )

    return handler


def register_tiktok_post_url_handlers(
    registry: WorkflowRegistry,
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[PostUrlWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
) -> WorkflowRegistry:
    """Register the TikTok Post URL handler into an injected Agent registry."""
    registry.register(
        TIKTOK_POST_URL_WORKFLOW_ID,
        build_tiktok_post_url_handler(
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
            tiktok_ai_hooks=tiktok_ai_hooks,
        ),
    )
    return registry


__all__ = [
    "TIKTOK_POST_URL_WORKFLOW_ID",
    "build_tiktok_post_url_handler",
    "register_tiktok_post_url_handlers",
    "run_tiktok_post_url",
]
