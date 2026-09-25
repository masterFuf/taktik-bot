"""The one launcher of a TikTok For You run, and its Agent handler.

`run_tiktok_for_you` is what the desktop bridge calls and what the handler registered as
`tiktok.automation.for_you` (the CLI) calls. What differs between the two is injected:
- `tiktok_startup() -> TikTokStartup`: clean restart, language, account; it supplies the device
  the run uses. Without it the injected `device` is used as is.
- `tiktok_ai_hooks(ai_config, language)`: installs the AI hooks the run asks for.
- `workflow_hook(workflow)`: wires the live events; defaults to the injected `notifier`.
- `on_finished(stats)`: reports the end of the run.
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.tiktok.actions.business.workflows._internal.agent_runtime import (
    attach_video_callbacks,
    merge_invocation_payload,
)
from taktik.core.social_media.tiktok.actions.business.workflows.for_you.payload import (
    for_you_config_from_payload,
)


TIKTOK_FOR_YOU_WORKFLOW_ID = "tiktok.automation.for_you"
ForYouWorkflowFactory = Callable[..., Any]
StartupProvider = Callable[[], Any]
AIHooks = Callable[[Mapping[str, Any], str], None]
WorkflowHook = Callable[[Any], None]
FinishedHook = Callable[[Any], None]


def _default_workflow_factory() -> ForYouWorkflowFactory:
    # Resolved at call time, so the module's class is the one a run gets.
    from taktik.core.social_media.tiktok.actions.business.workflows.for_you import workflow

    return workflow.ForYouWorkflow


def run_tiktok_for_you(
    payload: Mapping[str, Any],
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[ForYouWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
    workflow_hook: Optional[WorkflowHook] = None,
    on_finished: Optional[FinishedHook] = None,
) -> dict[str, Any]:
    """Start, hook, configure and run one For You session from a payload."""
    from taktik.core.social_media.tiktok.workflows.core.ai_hooks import (
        ai_config_from_payload,
        app_language_from_payload,
    )

    run_device = device
    if tiktok_startup is not None:
        run_device = tiktok_startup().device

    if tiktok_ai_hooks is not None:
        tiktok_ai_hooks(ai_config_from_payload(payload), app_language_from_payload(payload))

    config = for_you_config_from_payload(payload)
    factory = workflow_factory or _default_workflow_factory()
    workflow = factory(run_device, config)

    if workflow_hook is not None:
        workflow_hook(workflow)
    else:
        attach_video_callbacks(workflow, notifier)

    stats = workflow.run()
    if on_finished is not None:
        on_finished(stats)
    return {"success": True, "stats": stats.to_dict()}


def build_tiktok_for_you_handler(
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[ForYouWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
) -> WorkflowHandler:
    """Build an injectable For You handler for the Agent runtime."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        return run_tiktok_for_you(
            merge_invocation_payload(invocation, payload),
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
            tiktok_ai_hooks=tiktok_ai_hooks,
        )

    return handler


def register_tiktok_for_you_handlers(
    registry: WorkflowRegistry,
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[ForYouWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
) -> WorkflowRegistry:
    """Register TikTok For You handlers into an injected Agent registry."""
    registry.register(
        TIKTOK_FOR_YOU_WORKFLOW_ID,
        build_tiktok_for_you_handler(
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
            tiktok_ai_hooks=tiktok_ai_hooks,
        ),
    )
    return registry
