#!/usr/bin/env python3
"""TikTok follow-graph sync bridge — read the operated account's own lists.

One runner for `sync_following`, `sync_followers` and `sync_lists`: they differ by which list is
opened and which direction is written, and everything else — navigation, row reading, stopping,
persistence — is the same walk.

The run is `run_tiktok_sync_lists`, the launcher the Agent handlers
`tiktok.automation.sync_following`, `.sync_followers` and `.sync_lists` (and so the CLI) call too;
the list and the settings are read by the core (`sync_lists/payload.py`). This bridge only injects
the startup that prints on stdout, the live row events and the final stats.
"""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import (
    logger,
    send_error,
    send_message,
    send_status,
    set_workflow,
)
from bridges.tiktok.runtime.startup import tiktok_startup


def _startup(device_id: str):
    def start():
        from taktik.core.social_media.tiktok.workflows.runtime.startup import TikTokStartup

        manager, bot_username = tiktok_startup(device_id, fetch_profile=True)
        return TikTokStartup(device=manager.device_manager.device, bot_username=bot_username)

    return start


def _send_row(row: Dict[str, Any]) -> None:
    send_message(
        "sync_user_discovered",
        list_type=row.get("list_type"),
        username=row.get("username"),
        display_name=row.get("display_name"),
        relationship=row.get("relationship"),
        is_new=row.get("is_new"),
    )


def _bind_workflow(workflow, list_type: str, bot_username: str) -> None:
    set_workflow(workflow)
    workflow.set_on_row_callback(_send_row)
    send_message("workflow_start", target=bot_username, list_type=list_type)
    send_status("running", f"Reading the {list_type} list of @{bot_username}")


def _send_final_stats(stats, list_type: str) -> None:
    stats_dict = stats.to_dict()
    send_message("sync_stats", stats=stats_dict)
    send_message(
        "status",
        status="completed",
        message=(
            f"{stats.rows_seen} row(s) recorded, {stats.new_count} new"
            + (f", {stats.unidentified} without a readable handle" if stats.unidentified else "")
        ),
        completion_reason=stats_dict.get("completion_reason", "completed"),
    )
    logger.success(f"TikTok {list_type} sync completed: {stats_dict}")


def run_sync_lists_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok follow-graph sync. True when it ran without an error."""
    from taktik.core.social_media.tiktok.actions.business.workflows.sync_lists.payload import (
        list_type_from_payload,
    )

    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    list_type = list_type_from_payload(config)
    logger.info(f"Starting TikTok follow-graph sync ({list_type}) on device: {device_id}")
    send_status("starting", f"Initializing TikTok {list_type} sync on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.sync_lists.agent_handler import (
            SyncAccountUnknownError,
            run_tiktok_sync_lists,
        )

        try:
            result = run_tiktok_sync_lists(
                config,
                tiktok_startup=_startup(device_id),
                workflow_hook=_bind_workflow,
                on_finished=_send_final_stats,
            )
        except SyncAccountUnknownError as exc:
            send_error(str(exc))
            return False
        return result["success"]

    except ImportError as exc:
        error_msg = f"Import error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as exc:
        error_msg = f"TikTok sync workflow error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False


__all__ = ["run_sync_lists_workflow"]
