#!/usr/bin/env python3
"""
TikTok Followers Bridge - Followers workflow
"""

import time
from typing import Any, Dict

from bridges.tiktok.runtime.ipc import logger, send_error, send_status
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.automation.runtime.followers_events import (
    send_final_followers_stats,
)
from bridges.tiktok.workflows.automation.runtime.followers_planning import (
    calculate_target_distribution,
    max_profiles_for_target,
    should_stop_after_target,
)
from bridges.tiktok.workflows.automation.runtime.followers_request import validate_followers_workflow_request
from bridges.tiktok.workflows.automation.runtime.followers_stats import create_total_stats
from bridges.tiktok.workflows.automation.runtime.followers_target import run_followers_target
from taktik.core.social_media.tiktok.services.navigation.reset import return_to_tiktok_home


def run_followers_workflow(config: Dict[str, Any]):
    """Run the TikTok Followers workflow.

    Supports multi-target mode: if 'targets' array is provided, will process
    each target sequentially, distributing the max_followers limit across targets.
    Falls back to single 'searchQuery' for backwards compatibility.
    """
    request = validate_followers_workflow_request(config)
    if request is None:
        return False

    device_id = request.device_id
    bot_username = request.bot_username
    target_list = request.target_list

    logger.info(f"Starting TikTok Followers workflow on device: {device_id}")
    if bot_username:
        logger.info(f"Bot account: @{bot_username}")
    logger.info(f"Targets ({len(target_list)}): {', '.join(['@' + target for target in target_list])}")
    send_status("starting", f"Initializing TikTok Followers workflow on {device_id}")

    max_followers_total, profiles_per_target, extra_profiles = calculate_target_distribution(
        config,
        len(target_list),
    )

    logger.info(f"Distribution: {profiles_per_target} profiles per target (total: {max_followers_total})")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.followers.workflow import (
            FollowersConfig,
            FollowersWorkflow,
        )

        manager, fetched_bot_username = tiktok_startup(device_id, fetch_profile=True)
        effective_bot_username = fetched_bot_username or bot_username

        total_stats = create_total_stats()

        remaining_likes = config.get("maxLikesPerSession", 50)
        remaining_follows = config.get("maxFollowsPerSession", 20)
        completion_reason = "completed"

        for target_idx, current_target in enumerate(target_list):
            target_max_followers = max_profiles_for_target(
                target_idx,
                profiles_per_target,
                extra_profiles,
            )

            if remaining_likes <= 0 and remaining_follows <= 0:
                logger.info("Session limits reached, skipping remaining targets")
                break

            target_result = run_followers_target(
                FollowersWorkflow,
                FollowersConfig,
                manager,
                config,
                total_stats,
                target_list,
                target_idx,
                current_target,
                target_max_followers,
                remaining_likes,
                remaining_follows,
                effective_bot_username,
            )
            remaining_likes = target_result.remaining_likes
            remaining_follows = target_result.remaining_follows
            completion_reason = target_result.completion_reason

            if completion_reason in ["max_likes_reached", "max_follows_reached", "stopped_by_user"]:
                logger.info(f"Stopping multi-target workflow: {completion_reason}")
                break

            if should_stop_after_target(completion_reason):
                logger.warning(f"Target @{current_target} failed with error ({completion_reason}), stopping workflow")
                break

            if target_idx < len(target_list) - 1:
                logger.info("Switching to next target in 3 seconds...")
                time.sleep(2)
                if not return_to_tiktok_home(manager.device_manager.device, logger=logger):
                    logger.warning("Could not navigate to home, trying next target anyway...")

        total_stats["completion_reason"] = completion_reason

        logger.success(f"Multi-target workflow completed: {total_stats}")
        send_final_followers_stats(total_stats, len(target_list))

        return True

    except ImportError as exc:
        error_msg = f"Import error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as exc:
        error_msg = f"Followers workflow error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
