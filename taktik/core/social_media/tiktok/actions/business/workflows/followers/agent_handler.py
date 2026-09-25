"""The one launcher of a TikTok Followers run, and its Agent handler.

`run_tiktok_followers` is what the desktop bridge calls and what the handler registered as
`tiktok.automation.followers` (the CLI) calls. A run walks its targets in order, shares the
profile budget between them (never more profiles than the budget, so a budget below the number of
targets leaves the last ones out), carries the like and follow budgets over from one target to the
next, stops on a session limit, a stop or a failed target, and returns home between two targets.
What differs between hosts is injected:
- `tiktok_startup() -> TikTokStartup`: clean restart, language, account; supplies the device and
  the account the run acts as.
- `tiktok_ai_hooks(ai_config, language)`: installs the AI hooks the run asks for.
- `target_hook(workflow, target)`: wires the live events of one target; defaults to `notifier`.
- `on_finished(totals, targets)`: reports the end of the run.
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from loguru import logger

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
    followers_targets_from_payload,
    profile_budget_from_payload,
    profile_budgets,
    session_limits_from_payload,
)


TIKTOK_FOLLOWERS_WORKFLOW_ID = "tiktok.automation.followers"
FollowersWorkflowFactory = Callable[..., Any]
StartupProvider = Callable[[], Any]
AIHooks = Callable[[Any, str], None]
FinishedHook = Callable[[dict, list], None]

#: What a session adds up across its targets, in the shape the desktop reads (`followers_stats`).
#: `consecutive_known_usernames` is the last target's, not a sum.
SESSION_COUNTERS = (
    "followers_seen", "profiles_visited", "posts_watched", "likes", "favorites", "follows",
    "already_friends", "skipped", "known_usernames_seen", "new_usernames_seen",
    "consecutive_known_usernames", "errors",
)

#: A target ending on one of these ends the session.
_SESSION_ENDING_REASONS = frozenset({
    "max_likes_reached", "max_follows_reached", "stopped_by_user", "navigation_failed", "ERROR",
})


def new_session_totals() -> dict[str, Any]:
    return {counter: 0 for counter in SESSION_COUNTERS}


def _add_target_stats(totals: dict[str, Any], stats: Any) -> None:
    for counter in SESSION_COUNTERS:
        value = getattr(stats, counter)
        totals[counter] = value if counter == "consecutive_known_usernames" else totals[counter] + value


@dataclass
class FollowersTarget:
    """One target of a session, as a host sees it when its workflow is about to run."""

    index: int
    target: str
    targets: list[str]
    #: The session's totals before this target; the same dict all session long.
    totals: dict[str, Any]


TargetHook = Callable[[Any, FollowersTarget], None]


def _default_workflow_factory() -> FollowersWorkflowFactory:
    # Resolved at call time, so the module's class is the one a run gets.
    from taktik.core.social_media.tiktok.actions.business.workflows.followers import workflow

    return workflow.FollowersWorkflow


def _return_home(device) -> bool:
    from taktik.core.social_media.tiktok.services.navigation import reset

    return reset.return_to_tiktok_home(device, logger=logger)


def run_tiktok_followers(
    payload: Any,
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[FollowersWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
    target_hook: Optional[TargetHook] = None,
    on_finished: Optional[FinishedHook] = None,
) -> dict[str, Any]:
    """Start, hook and run every target of one Followers session from a payload."""
    from taktik.core.social_media.tiktok.workflows.core.ai_hooks import (
        ai_config_from_payload,
        app_language_from_payload,
    )

    targets = followers_targets_from_payload(payload)
    if not targets:
        raise ValueError("TikTok followers requires at least one target (targets or searchQuery)")

    run_device = device
    bot_username = bot_username_from_payload(payload)
    if tiktok_startup is not None:
        started = tiktok_startup()
        run_device = started.device
        bot_username = started.bot_username or bot_username

    if tiktok_ai_hooks is not None:
        tiktok_ai_hooks(ai_config_from_payload(payload), app_language_from_payload(payload))

    settings = followers_settings_from_payload(payload)
    total_budget = profile_budget_from_payload(payload)
    shares = profile_budgets(total_budget, len(targets))
    # A target without a share is not visited: the budget caps the run, not the list.
    targets = [target for target, share in zip(targets, shares) if share > 0]
    budgets = [share for share in shares if share > 0]
    remaining_likes, remaining_follows = session_limits_from_payload(payload)
    logger.info(f"Distribution: {budgets} profiles per target (total: {total_budget})")

    totals = new_session_totals()
    factory = workflow_factory or _default_workflow_factory()
    completion_reason = "completed"

    for index, target in enumerate(targets):
        if remaining_likes <= 0 and remaining_follows <= 0:
            logger.info("Session limits reached, skipping remaining targets")
            break

        logger.info(f"Target {index + 1}/{len(targets)}: @{target}")
        logger.info(f"Max profiles for this target: {budgets[index]}")
        config = followers_config_for_target(
            settings,
            search_query=target,
            max_followers=budgets[index],
            max_likes_per_session=remaining_likes,
            max_follows_per_session=remaining_follows,
        )
        workflow = factory(run_device, config)
        if target_hook is not None:
            target_hook(workflow, FollowersTarget(index=index, target=target, targets=targets, totals=totals))
        else:
            attach_profile_callbacks(workflow, notifier)

        logger.info(f"Running followers workflow for @{target}...")
        stats = workflow.run(bot_username=bot_username)
        _add_target_stats(totals, stats)
        remaining_likes -= stats.likes
        remaining_follows -= stats.follows
        completion_reason = getattr(stats, "completion_reason", "unknown")
        logger.info(f"Target @{target} completed: {stats.profiles_visited} profiles, {stats.likes} likes")

        if completion_reason in _SESSION_ENDING_REASONS:
            logger.warning(f"Stopping multi-target workflow after @{target}: {completion_reason}")
            break

        if index < len(targets) - 1:
            logger.info("Switching to next target...")
            time.sleep(2)
            if not _return_home(run_device):
                logger.warning("Could not navigate to home, trying next target anyway...")

    totals["completion_reason"] = completion_reason
    logger.success(f"Multi-target workflow completed: {totals}")
    if on_finished is not None:
        on_finished(totals, targets)
    return {"success": True, "targets": targets, "stats": totals}


def build_tiktok_followers_handler(
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[FollowersWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
) -> WorkflowHandler:
    """Build the Followers handler for the Agent runtime."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        return run_tiktok_followers(
            merge_invocation_payload(invocation, payload),
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
            tiktok_ai_hooks=tiktok_ai_hooks,
        )

    return handler


def register_tiktok_followers_handlers(
    registry: WorkflowRegistry,
    *,
    device=None,
    notifier=None,
    workflow_factory: Optional[FollowersWorkflowFactory] = None,
    tiktok_startup: Optional[StartupProvider] = None,
    tiktok_ai_hooks: Optional[AIHooks] = None,
) -> WorkflowRegistry:
    """Register TikTok followers handlers into an injected Agent registry."""
    registry.register(
        TIKTOK_FOLLOWERS_WORKFLOW_ID,
        build_tiktok_followers_handler(
            device=device,
            notifier=notifier,
            workflow_factory=workflow_factory,
            tiktok_startup=tiktok_startup,
            tiktok_ai_hooks=tiktok_ai_hooks,
        ),
    )
    return registry
