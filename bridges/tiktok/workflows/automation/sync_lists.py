#!/usr/bin/env python3
"""TikTok follow-graph sync bridge — read the operated account's own lists.

One runner for both `sync_following` and `sync_followers`: the two differ by which list is
opened and which direction is written, and everything else — navigation, row reading, stopping,
persistence — is the same walk. A second runner would be a second place for that walk to drift.
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

#: Bridge workflow type -> which list(s) the run reads.
LIST_TYPE_BY_WORKFLOW = {
    "sync_following": "following",
    "sync_followers": "followers",
    "sync_lists": "both",
}


def resolve_list_type(config: Dict[str, Any]) -> str:
    """Which list this run is about, from the workflow type or an explicit override."""
    explicit = str(config.get("listType") or "").strip().lower()
    if explicit in ("following", "followers", "both"):
        return explicit
    return LIST_TYPE_BY_WORKFLOW.get(config.get("workflowType"), "following")


def run_sync_lists_workflow(config: Dict[str, Any]) -> bool:
    """Run the TikTok follow-graph sync."""
    device_id = config.get("deviceId")
    if not device_id:
        send_error("No device ID provided")
        return False

    list_type = resolve_list_type(config)
    bot_username = config.get("botUsername")

    logger.info(f"Starting TikTok follow-graph sync ({list_type}) on device: {device_id}")
    send_status("starting", f"Initializing TikTok {list_type} sync on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.sync_lists import (
            SyncListsConfig,
            SyncListsWorkflow,
        )

        manager, fetched_bot_username = tiktok_startup(device_id, fetch_profile=True)
        effective_bot_username = fetched_bot_username or bot_username
        if not effective_bot_username:
            # Without the acting account there is nothing to attach the graph to, and writing it
            # under a guessed account is worse than not writing it.
            send_error("Could not identify the acting TikTok account")
            logger.error("No bot username: refusing to write a follow graph with no owner")
            return False

        workflow_config = SyncListsConfig(
            list_type=list_type,
            incremental=bool(config.get("incremental", True)),
            max_scrolls=int(config.get("maxScrolls", 60)),
            resolve_missing_handles=bool(config.get("resolveMissingHandles", False)),
            max_resolutions=int(config.get("maxResolutions", 50)),
            min_delay=float(config.get("minDelay", 0.6)),
            max_delay=float(config.get("maxDelay", 1.4)),
        )

        workflow = SyncListsWorkflow(manager.device_manager.device, workflow_config)
        set_workflow(workflow)

        def on_row(row: Dict[str, Any]) -> None:
            send_message(
                "sync_user_discovered",
                list_type=row.get("list_type"),
                username=row.get("username"),
                display_name=row.get("display_name"),
                relationship=row.get("relationship"),
                is_new=row.get("is_new"),
            )

        workflow.set_on_row_callback(on_row)

        send_message("workflow_start", target=effective_bot_username, list_type=list_type)
        send_status("running", f"Reading the {list_type} list of @{effective_bot_username}")

        stats = workflow.run(bot_username=effective_bot_username)
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
        return stats.errors == 0

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


__all__ = ["LIST_TYPE_BY_WORKFLOW", "resolve_list_type", "run_sync_lists_workflow"]
