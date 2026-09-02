#!/usr/bin/env python3
"""TikTok Target Profiles bridge — engage a hand-picked list of accounts.

The followers runner distributes a budget across several targets and engages THEIR followers.
This one is flat: the list IS the work. One pass, one session, one stats payload.

The stats event stays `followers_stats`, and the payload keeps the followers shape, because the
workflow returns `FollowersStats` and Electron already knows how to read it. Inventing a second
event here would mean a second reader on the app side for numbers that are the same numbers.
"""

from typing import Any, Dict, List

from bridges.tiktok.runtime.ipc import (
    logger,
    send_action,
    send_error,
    send_message,
    send_pause,
    send_status,
    set_workflow,
)
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.automation.runtime.ai import install_profile_ai_hooks
from bridges.tiktok.workflows.automation.runtime.followers_planning import (
    build_followers_config,
)
from bridges.tiktok.workflows.automation.runtime.followers_stats import create_total_stats
from bridges.tiktok.workflows.automation.runtime.workflow_callbacks import wire_workflow_callbacks


def _bridge_log(level: str, message: str) -> None:
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def build_profile_list(config: Dict[str, Any]) -> List[str]:
    """Read the list of profiles to engage, in any of the payload shapes the app may send.

    Deliberately NOT `build_target_list`: that helper falls back to `searchQuery`, which for the
    followers workflow means "the account whose followers we want". Reusing it here would turn a
    run launched without a list into a run against one arbitrary account — the exact silent
    wrong-target failure this workflow has to avoid.
    """
    for key in ("profiles", "targetProfiles", "usernames"):
        raw = config.get(key)
        if raw:
            # Filtered AFTER stripping the at-sign, not before: a bare "@" is truthy and would
            # otherwise survive as an empty handle — dropped later by the workflow, but only
            # after being logged as a target and counted in the run's budget.
            cleaned = (str(item or "").strip().lstrip("@").strip() for item in raw)
            return [name for name in cleaned if name]
    return []


def run_target_profiles_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok Target Profiles workflow."""
    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    bot_username = config.get("botUsername")
    profiles = build_profile_list(config)
    if not profiles:
        send_error("No profile provided")
        logger.error("No profile provided for the target-profiles workflow")
        return False

    logger.info(f"Starting TikTok Target Profiles workflow on device: {device_id}")
    if bot_username:
        logger.info(f"Bot account: @{bot_username}")
    logger.info(f"Profiles ({len(profiles)}): {', '.join(['@' + name for name in profiles])}")
    send_status("starting", f"Initializing TikTok Target Profiles workflow on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.target_profiles import (
            TargetProfilesConfig,
            TargetProfilesWorkflow,
        )

        manager, fetched_bot_username = tiktok_startup(device_id, fetch_profile=True)
        effective_bot_username = fetched_bot_username or bot_username

        install_profile_ai_hooks(config, log=_bridge_log)

        # The budget defaults to the length of the list: a list of 12 profiles asks for 12
        # visits, not for the followers workflow's default of 20.
        max_profiles = config.get("maxProfiles") or config.get("maxFollowers") or len(profiles)

        # Same builder as the followers workflow, so every interaction knob — probabilities,
        # watch times, delays, pauses, filters — is read from the payload in exactly one place.
        workflow_config = build_followers_config(
            TargetProfilesConfig,
            config,
            "",  # no source account: the list IS the target
            max_profiles,
            config.get("maxLikesPerSession", 50),
            config.get("maxFollowsPerSession", 20),
        )
        workflow_config.usernames = profiles

        workflow = TargetProfilesWorkflow(manager.device_manager.device, workflow_config)
        set_workflow(workflow)

        send_message("workflow_start", target="", targets=profiles, current_target_index=0)

        total_stats = create_total_stats()
        _wire_callbacks(workflow, total_stats, len(profiles))

        send_status("running", f"Engaging {len(profiles)} profiles")

        stats = workflow.run(bot_username=effective_bot_username)
        stats_dict = stats.to_dict()

        send_message("followers_stats", stats=stats_dict)
        send_message(
            "status",
            status="completed",
            message=f"Visited {stats.profiles_visited} of {len(profiles)} profiles",
            completion_reason=stats_dict.get("completion_reason", "completed"),
        )

        logger.success(f"Target Profiles workflow completed: {stats_dict}")
        return True

    except ImportError as exc:
        error_msg = f"Import error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as exc:
        error_msg = f"Target Profiles workflow error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


def _wire_callbacks(workflow: Any, total_stats: Dict[str, Any], total_profiles: int) -> None:
    """Live bridge callbacks. Single pass, so the totals ARE the run's stats.

    This function used to wire the four callbacks by hand and knew nothing of the profile one --
    so every avatar this workflow captured was dropped on the floor. It now delegates, and only
    keeps what is genuinely its own: a single-pass run reports its totals directly.
    """

    def on_stats(stats_dict):
        payload = {**total_stats, **stats_dict}
        payload["total_targets"] = total_profiles
        send_message("followers_stats", stats=payload)

    wire_workflow_callbacks(workflow, on_stats=on_stats)


__all__ = ["build_profile_list", "run_target_profiles_workflow"]
