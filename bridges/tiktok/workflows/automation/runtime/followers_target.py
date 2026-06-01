"""Single-target execution for the TikTok Followers bridge runner."""

from dataclasses import dataclass
from typing import Any, Dict, List, Type

from bridges.tiktok.runtime.ipc import logger, send_status, set_workflow
from bridges.tiktok.workflows.automation.runtime.followers_events import (
    send_followers_workflow_start,
    send_target_switch,
)
from bridges.tiktok.workflows.automation.runtime.followers_planning import build_followers_config
from bridges.tiktok.workflows.automation.runtime.followers_stats import (
    record_target_stats,
    wire_followers_callbacks,
)


@dataclass
class FollowersTargetResult:
    """Result of one target pass in a multi-target Followers session."""

    completion_reason: str
    remaining_likes: int
    remaining_follows: int


def run_followers_target(
    followers_workflow_class: Type[Any],
    followers_config_class: Type[Any],
    manager: Any,
    config: Dict[str, Any],
    total_stats: Dict[str, Any],
    target_list: List[str],
    target_idx: int,
    current_target: str,
    target_max_followers: int,
    remaining_likes: int,
    remaining_follows: int,
    effective_bot_username: str | None,
) -> FollowersTargetResult:
    """Run the Followers workflow for one target and update aggregate stats."""
    logger.info(f"\n{'='*50}")
    logger.info(f"ðŸŽ¯ Target {target_idx + 1}/{len(target_list)}: @{current_target}")
    logger.info(f"ðŸ“Š Max profiles for this target: {target_max_followers}")
    logger.info(f"{'='*50}")

    send_target_switch(current_target, target_idx, target_list)

    workflow_config = build_followers_config(
        followers_config_class,
        config,
        current_target,
        target_max_followers,
        remaining_likes,
        remaining_follows,
    )

    send_status("running", f"Processing target {target_idx + 1}/{len(target_list)}: @{current_target}")

    workflow = followers_workflow_class(manager.device_manager.device, workflow_config)
    set_workflow(workflow)

    send_followers_workflow_start(current_target, target_list, target_idx)

    wire_followers_callbacks(
        workflow,
        total_stats,
        current_target,
        target_idx,
        len(target_list),
    )

    logger.info(f"â–¶ï¸ Running followers workflow for @{current_target}...")
    stats = workflow.run(bot_username=effective_bot_username)

    record_target_stats(total_stats, stats)

    next_remaining_likes = remaining_likes - stats.likes
    next_remaining_follows = remaining_follows - stats.follows
    completion_reason = getattr(stats, "completion_reason", "unknown")

    logger.info(
        f"âœ… Target @{current_target} completed: "
        f"{stats.profiles_visited} profiles, {stats.likes} likes"
    )

    return FollowersTargetResult(
        completion_reason=completion_reason,
        remaining_likes=next_remaining_likes,
        remaining_follows=next_remaining_follows,
    )
