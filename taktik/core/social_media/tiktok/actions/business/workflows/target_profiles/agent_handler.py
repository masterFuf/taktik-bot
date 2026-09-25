"""The one launcher of a TikTok Target Profiles run, and its Agent handler.

`run_tiktok_target_profiles` is what the desktop bridge calls and what the handler registered as
`tiktok.automation.target_profiles` (the CLI) calls: one pass over a hand-picked list, with the
Followers interaction settings. What differs between hosts is injected:
- `tiktok_startup() -> TikTokStartup`: clean restart, language, account; supplies the device and
  the account the run acts as.
- `tiktok_ai_hooks(ai_config, language)`: installs the AI hooks the run asks for.
- `workflow_hook(workflow, profiles)`: wires the live events; defaults to `notifier`.
- `on_finished(stats, profiles)`: reports the end of the run.
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
    followers_config_for_target,
    followers_settings_from_payload,
    session_limits_from_payload,
)
from taktik.core.social_media.tiktok.actions.business.workflows.target_profiles.payload import (
    profile_visit_budget,
    target_profiles_from_payload,
)


TIKTOK_TARGET_PROFILES_WORKFLOW_ID = "tiktok.automation.target_profiles"
TargetProfilesWorkflowFactory = Callable[..., Any]
StartupProvider = Callable[[], Any]
AIHooks = Callable[[Any, str], None]
WorkflowHook = Callable[[Any, list], None]
FinishedHook = Callable[[Any, list], None]


def _default_workflow_factory() -> TargetProfilesWorkflowFactory:
    # Resolved at call time, so the module's class is the one a run gets.
    from taktik.core.social_media.tiktok.actions.business.workflows.target_profiles import workflow

    return workflow.TargetProfilesWorkflow


def run_tiktok_target_profiles(
    payload: Any,
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[TargetProfilesWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
    workflow_hook: Optional[WorkflowHook] = None,
    on_finished: Optional[FinishedHook] = None,
) -> dict[str, Any]:
    """Start, hook, configure and run one pass over a list of profiles from a payload."""
    from taktik.core.social_media.tiktok.actions.business.workflows.target_profiles.workflow import (
        TargetProfilesConfig,
    )
    from taktik.core.social_media.tiktok.workflows.core.ai_hooks import (
        ai_config_from_payload,
        app_language_from_payload,
    )

    profiles = target_profiles_from_payload(payload)
    if not profiles:
        raise ValueError("TikTok target profiles requires a non-empty profiles list")

    run_device = device
    bot_username = bot_username_from_payload(payload)
    if tiktok_startup is not None:
        started = tiktok_startup()
        run_device = started.device
        bot_username = started.bot_username or bot_username

    if tiktok_ai_hooks is not None:
        tiktok_ai_hooks(ai_config_from_payload(payload), app_language_from_payload(payload))

    max_likes, max_follows = session_limits_from_payload(payload)
    config = followers_config_for_target(
        followers_settings_from_payload(payload),
        search_query="",  # no source account: the list is the target
        max_followers=profile_visit_budget(payload, profiles),
        max_likes_per_session=max_likes,
        max_follows_per_session=max_follows,
        config_class=TargetProfilesConfig,
        usernames=profiles,
    )
    workflow = (workflow_factory or _default_workflow_factory())(run_device, config)
    if workflow_hook is not None:
        workflow_hook(workflow, profiles)
    else:
        attach_profile_callbacks(workflow, notifier)

    stats = workflow.run(bot_username=bot_username)
    if on_finished is not None:
        on_finished(stats, profiles)
    return {"success": True, "profiles": profiles, "stats": stats.to_dict()}


def build_tiktok_target_profiles_handler(
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[TargetProfilesWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
) -> WorkflowHandler:
    """Build the Target Profiles handler for the Agent runtime."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        return run_tiktok_target_profiles(
            merge_invocation_payload(invocation, payload),
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
            tiktok_ai_hooks=tiktok_ai_hooks,
        )

    return handler


def register_tiktok_target_profiles_handlers(
    registry: WorkflowRegistry,
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[TargetProfilesWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
) -> WorkflowRegistry:
    """Register the TikTok Target Profiles handler into an injected Agent registry."""
    registry.register(
        TIKTOK_TARGET_PROFILES_WORKFLOW_ID,
        build_tiktok_target_profiles_handler(
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
            tiktok_ai_hooks=tiktok_ai_hooks,
        ),
    )
    return registry
