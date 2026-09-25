#!/usr/bin/env python3
"""
TikTok Search Bridge - Search/Hashtag workflow

The run is `run_tiktok_search`, the launcher the Agent handlers `tiktok.automation.search` and
`.hashtag` (and so the CLI) call too. Called by name rather than through the registry so the app's
config contract test can follow the payload. This bridge only injects what is specific to the
desktop: the startup that prints on stdout, the AI hooks wired to stdout, the per-query events and
live callbacks, the final stats.
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
from bridges.tiktok.workflows.automation.runtime.ai import install_run_ai_hooks
from bridges.tiktok.runtime.video_callbacks import send_final_video_stats
from bridges.tiktok.workflows.automation.runtime.search_callbacks import (
    setup_search_workflow_callbacks,
)


def _bridge_log(level: str, message: str) -> None:
    """(level, message) -> loguru, the shape the AI hooks expect. Same helper as the Followers
    and Target bridges — copied rather than shared because three lines behind an import is a
    module nobody would open twice."""
    getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def _startup(device_id: str):
    def start():
        from taktik.core.social_media.tiktok.workflows.runtime.startup import TikTokStartup

        manager, bot_username = tiktok_startup(device_id, fetch_profile=True)
        return TikTokStartup(device=manager.device_manager.device, bot_username=bot_username)

    return start


def _ai_hooks(ai_config, language) -> None:
    install_run_ai_hooks(ai_config, language, log=_bridge_log)


def _query_hook(sent_pics: set):
    """Per query: announce it, then wire the live callbacks on top of the session's totals."""

    def bind(workflow, query) -> None:
        if query.index == 0:
            send_message(
                "search_workflow_start",
                current_target=query.query,
                targets=query.queries,
                current_target_index=query.index,
                workflow_type=query.workflow_type,
            )
        else:
            send_message(
                "search_target_switch",
                current_target=query.query,
                target_index=query.index,
                total_targets=len(query.queries),
                workflow_type=query.workflow_type,
            )

        send_status("running", f"Searching for: {query.label}")
        set_workflow(workflow)
        totals = query.totals
        setup_search_workflow_callbacks(
            workflow,
            {
                "videos_watched": totals.videos_watched,
                "videos_liked": totals.videos_liked,
                "users_followed": totals.users_followed,
                "videos_favorited": totals.videos_favorited,
                "videos_skipped": totals.videos_skipped,
                "errors": totals.errors,
            },
            sent_pics,
        )

    return bind


def run_search_workflow(config: Dict[str, Any]):
    """Run the TikTok Search/Hashtag workflow."""
    from taktik.core.social_media.tiktok.actions.business.workflows.search.payload import (
        query_label,
        search_queries_from_payload,
    )

    device_id = config.get("deviceId")
    workflow_type = str(config.get("workflowType") or "search").strip().lower()
    search_queries = search_queries_from_payload(config, hashtag=workflow_type == "hashtag")

    if not device_id:
        send_error("No device ID provided")
        return False

    if not search_queries:
        send_error("No search query provided")
        return False

    logger.info(f"Starting TikTok Search workflow on device: {device_id}")
    logger.info(
        f"Search queries ({len(search_queries)}): "
        f"{', '.join(query_label(query, workflow_type) for query in search_queries)}"
    )
    send_status("starting", f"Initializing TikTok Search workflow on {device_id}")

    try:
        from taktik.core.social_media.tiktok.actions.business.workflows.search.agent_handler import (
            run_tiktok_search,
        )

        run_tiktok_search(
            config,
            workflow_type=workflow_type,
            tiktok_startup=_startup(device_id),
            tiktok_ai_hooks=_ai_hooks,
            query_hook=_query_hook(set()),
            on_finished=lambda totals: send_final_video_stats(totals, "Search workflow"),
        )
        return True

    except ImportError as exc:
        error_msg = f"Import error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
    except Exception as exc:
        error_msg = f"Search workflow error: {exc}"
        logger.error(error_msg)
        send_error(error_msg)
        return False
