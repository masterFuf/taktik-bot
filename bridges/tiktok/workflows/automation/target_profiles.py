#!/usr/bin/env python3
"""TikTok Target Profiles bridge — engage a hand-picked list of accounts.

The followers runner distributes a budget across several targets and engages THEIR followers.
This one is flat: the list IS the work. One pass, one session, one stats payload.

The run is `run_tiktok_target_profiles`, the launcher the Agent handler
`tiktok.automation.target_profiles` (and so the CLI) calls too; the list and the settings are read
by the core (`target_profiles/payload.py`, `followers/payload.py`). This bridge only injects the
startup that prints on stdout, the AI hooks wired to stdout, the live callbacks and the final
stats.

The stats event stays `followers_stats`, and the payload keeps the followers shape, because the
workflow returns `FollowersStats` and Electron already knows how to read it. Inventing a second
event here would mean a second reader on the app side for numbers that are the same numbers.
"""

from typing import Any, Dict, List

from bridges.tiktok.runtime.ipc import (
    logger,
    send_error,
    send_message,
    send_status,
    set_workflow,
)
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.workflows.automation.runtime.ai import install_run_ai_hooks
from bridges.tiktok.workflows.automation.runtime.workflow_callbacks import wire_single_pass_callbacks
from taktik.core.social_media.tiktok.actions.business.workflows.followers.agent_handler import (
    new_session_totals,
)


def _bridge_log(level: str, message: str) -> None:
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def _startup(device_id: str):
    def start():
        from taktik.core.social_media.tiktok.workflows.runtime.startup import TikTokStartup

        manager, bot_username = tiktok_startup(device_id, fetch_profile=True)
        return TikTokStartup(device=manager.device_manager.device, bot_username=bot_username)

    return start


def _ai_hooks(ai_config, language) -> None:
    install_run_ai_hooks(ai_config, language, log=_bridge_log)


def _bind_workflow(workflow, profiles: List[str]) -> None:
    set_workflow(workflow)
    send_message("workflow_start", target="", targets=profiles, current_target_index=0)
    wire_single_pass_callbacks(workflow, new_session_totals(), total_targets=len(profiles))
    send_status("running", f"Engaging {len(profiles)} profiles")


def _send_final_stats(stats, profiles: List[str]) -> None:
    stats_dict = stats.to_dict()
    send_message("followers_stats", stats=stats_dict)
    send_message(
        "status",
        status="completed",
        message=f"Visited {stats.profiles_visited} of {len(profiles)} profiles",
        completion_reason=stats_dict.get("completion_reason", "completed"),
    )
    logger.success(f"Target Profiles workflow completed: {stats_dict}")


def run_target_profiles_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok Target Profiles workflow."""
    from taktik.core.social_media.tiktok.actions.business.workflows.target_profiles.payload import (
        target_profiles_from_payload,
    )

    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    profiles = target_profiles_from_payload(config)
    if not profiles:
        send_error("No profile provided")
        logger.error("No profile provided for the target-profiles workflow")
        return False

    logger.info(f"Starting TikTok Target Profiles workflow on device: {device_id}")
    logger.info(f"Profiles ({len(profiles)}): {', '.join(['@' + name for name in profiles])}")
    send_status("starting", f"Initializing TikTok Target Profiles workflow on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.target_profiles.agent_handler import (
            run_tiktok_target_profiles,
        )

        run_tiktok_target_profiles(
            config,
            tiktok_startup=_startup(device_id),
            tiktok_ai_hooks=_ai_hooks,
            workflow_hook=_bind_workflow,
            on_finished=_send_final_stats,
        )
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


__all__ = ["run_target_profiles_workflow"]
