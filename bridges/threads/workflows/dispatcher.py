#!/usr/bin/env python3
"""Threads Bridge — main dispatcher for Threads workflows.

Routes to specific workflow bridges based on `workflowType` in the config.
Mirrors the TikTok dispatcher pattern. Workflows are added incrementally as
UI selectors are captured from real devices.

Current state (MVP scaffolding): the bridge can boot, parse config, emit
status/stats over IPC and run a no-op "follow" workflow stub so that the
Electron front can validate the end-to-end pipeline before the real action
logic lands.
"""

import json
import os
import signal
import sys

# Bootstrap sys.path so absolute imports work when run as a standalone script
_bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _bot_dir not in sys.path:
    sys.path.insert(0, _bot_dir)

from bridges.threads.base import (
    logger,
    send_error,
    send_log,
    send_status,
    send_threads_action,
    send_threads_profile_visit,
    send_threads_stats,
    signal_handler,
)


def _run_feed(config: dict) -> bool:
    """Threads Feed & Interact workflow.

    Iterates the home feed, visits each post author's profile and applies
    per-action probabilities (follow / like / repost).
    """
    from taktik.core.social_media.threads.workflows import (
        ActionProbabilities,
        FeedInteractConfig,
        InteractStats,
        ProfileFilters,
        run_feed_and_interact,
    )

    device_id = config.get("deviceId", "unknown")
    action_cfg = config.get("actionProbabilities") or {}
    filters_cfg = config.get("filters") or {}

    feed_cfg = FeedInteractConfig(
        device_id=device_id,
        max_profiles=int(config.get("maxProfiles", config.get("maxFollows", 10))),
        min_delay_seconds=float(config.get("minDelaySeconds", 2.0)),
        max_delay_seconds=float(config.get("maxDelaySeconds", 5.0)),
        max_likes_per_profile=int(config.get("maxLikesPerProfile", 2)),
        actions=ActionProbabilities(
            follow=int(action_cfg.get("follow", 80)),
            like=int(action_cfg.get("like", 50)),
            repost=int(action_cfg.get("repost", 0)),
            comment=int(action_cfg.get("comment", 0)),
        ),
        filters=ProfileFilters(
            min_followers=int(filters_cfg.get("minFollowers", 0)),
            max_followers=int(filters_cfg.get("maxFollowers", 10_000_000)),
            bio_keywords_include=list(filters_cfg.get("bioKeywordsInclude") or []),
            bio_keywords_exclude=list(filters_cfg.get("bioKeywordsExclude") or []),
        ),
    )

    send_log("info",
             f"[threads:feed] device={device_id} max={feed_cfg.max_profiles} "
             f"probs(follow={feed_cfg.actions.follow}% like={feed_cfg.actions.like}% "
             f"repost={feed_cfg.actions.repost}% comment={feed_cfg.actions.comment}%)")
    send_status("running", f"Threads feed workflow on {device_id}")

    def _forward_log(level: str, message: str) -> None:
        send_log(level, message)

    def _forward_stats(stats: InteractStats) -> None:
        send_threads_stats(**stats.as_dict())

    def _forward_profile_visit(info: dict) -> None:
        send_threads_profile_visit(
            username=info.get("username") or "",
            followers=info.get("followers"),
            is_private=bool(info.get("is_private", False)),
        )

    def _forward_action(action: str, username: str, details: dict) -> None:
        send_threads_action(action, username, details)

    try:
        stats = run_feed_and_interact(
            feed_cfg,
            on_log=_forward_log,
            on_stats=_forward_stats,
            on_profile_visit=_forward_profile_visit,
            on_action=_forward_action,
        )
    except Exception as exc:  # noqa: BLE001
        send_error(f"Threads feed workflow crashed: {exc}", error_code="threads.workflow_crash")
        logger.exception("Threads feed workflow crashed")
        return False

    send_threads_stats(**stats.as_dict())
    summary = (f"visited={stats.profiles_visited} follows={stats.follows} "
               f"likes={stats.likes} reposts={stats.reposts} errors={stats.errors}")
    send_status("completed", f"Threads feed workflow finished \u2014 {summary}")
    return stats.errors == 0 or (stats.follows + stats.likes + stats.reposts) > 0


def _run_follow(config: dict) -> bool:
    """Real Threads Search-and-Interact workflow (MVP).

    Opens Threads, searches the `searchQuery`, switches to the "Related profiles"
    tab and iterates profiles applying per-action probabilities (follow / like /
    repost). Smart-comment is deferred to step D (taktik-agent integration).
    """
    from taktik.core.social_media.threads.workflows import (
        ActionProbabilities,
        InteractStats,
        ProfileFilters,
        SearchInteractConfig,
        run_search_and_interact,
    )

    device_id = config.get("deviceId", "unknown")

    # Back-compat: accept either `searchQuery` (new) or `targets[0]` (legacy).
    query = (config.get("searchQuery") or "").strip()
    if not query:
        legacy_targets = config.get("targets") or config.get("targetAccounts") or []
        if isinstance(legacy_targets, str):
            legacy_targets = [legacy_targets]
        if legacy_targets:
            query = str(legacy_targets[0]).strip().lstrip("@")

    if not query:
        send_error("No search query provided", error_code="threads.no_query")
        return False

    action_cfg = config.get("actionProbabilities") or {}
    filters_cfg = config.get("filters") or {}

    interact_cfg = SearchInteractConfig(
        device_id=device_id,
        search_query=query,
        max_profiles=int(config.get("maxProfiles", config.get("maxFollows", 10))),
        min_delay_seconds=float(config.get("minDelaySeconds", 2.0)),
        max_delay_seconds=float(config.get("maxDelaySeconds", 5.0)),
        max_likes_per_profile=int(config.get("maxLikesPerProfile", 2)),
        actions=ActionProbabilities(
            follow=int(action_cfg.get("follow", 80)),
            like=int(action_cfg.get("like", 50)),
            repost=int(action_cfg.get("repost", 0)),
            comment=int(action_cfg.get("comment", 0)),
        ),
        filters=ProfileFilters(
            min_followers=int(filters_cfg.get("minFollowers", 0)),
            max_followers=int(filters_cfg.get("maxFollowers", 10_000_000)),
            bio_keywords_include=list(filters_cfg.get("bioKeywordsInclude") or []),
            bio_keywords_exclude=list(filters_cfg.get("bioKeywordsExclude") or []),
        ),
    )

    send_log("info",
             f"[threads:search] device={device_id} query={query!r} "
             f"max={interact_cfg.max_profiles} "
             f"probs(follow={interact_cfg.actions.follow}% like={interact_cfg.actions.like}% "
             f"repost={interact_cfg.actions.repost}% comment={interact_cfg.actions.comment}%)")
    send_status("running", f"Threads search workflow on {device_id}")

    def _forward_log(level: str, message: str) -> None:
        send_log(level, message)

    def _forward_stats(stats: InteractStats) -> None:
        send_threads_stats(**stats.as_dict())

    def _forward_profile_visit(info: dict) -> None:
        send_threads_profile_visit(
            username=info.get("username") or "",
            followers=info.get("followers"),
            is_private=bool(info.get("is_private", False)),
        )

    def _forward_action(action: str, username: str, details: dict) -> None:
        send_threads_action(action, username, details)

    try:
        stats = run_search_and_interact(
            interact_cfg,
            on_log=_forward_log,
            on_stats=_forward_stats,
            on_profile_visit=_forward_profile_visit,
            on_action=_forward_action,
        )
    except Exception as exc:  # noqa: BLE001 — top-level guard
        send_error(f"Threads search workflow crashed: {exc}", error_code="threads.workflow_crash")
        logger.exception("Threads search workflow crashed")
        return False

    send_threads_stats(**stats.as_dict())
    summary = (f"visited={stats.profiles_visited} follows={stats.follows} "
               f"likes={stats.likes} reposts={stats.reposts} errors={stats.errors}")
    send_status("completed", f"Threads search workflow finished — {summary}")
    return stats.errors == 0 or (stats.follows + stats.likes + stats.reposts) > 0


def main() -> None:
    """Main entry point — dispatch to the appropriate Threads workflow."""
    # Install shared signal handlers (SIGINT/SIGTERM) for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if len(sys.argv) < 2:
        send_error("No config file provided")
        logger.error("No config file provided")
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        send_error(f"Failed to load config: {e}")
        logger.error(f"Failed to load config from {config_path}: {e}")
        sys.exit(1)

    workflow_type = config.get("workflowType", "follow")
    device_id = config.get("deviceId", "unknown")
    logger.info(f"🧵 Threads bridge starting — workflow={workflow_type} device={device_id}")

    try:
        if workflow_type in ("follow", "target"):
            success = _run_follow(config)
        elif workflow_type == "feed":
            success = _run_feed(config)
        else:
            send_error(f"Unknown workflow type: {workflow_type}", error_code="threads.unknown_workflow")
            logger.error(f"Unknown workflow type: {workflow_type}")
            sys.exit(1)

        if success:
            logger.success(f"✅ Threads {workflow_type} workflow completed")
            sys.exit(0)
        logger.error(f"❌ Threads {workflow_type} workflow failed")
        sys.exit(1)

    except ImportError as e:
        send_error(f"Failed to import workflow module: {e}")
        logger.error(f"Import error: {e}")
        sys.exit(1)
    except Exception as e:
        send_error(f"Workflow error: {e}")
        logger.exception(f"Unexpected error in {workflow_type} workflow: {e}")
        sys.exit(1)
    finally:
        from bridges.common.device.app_manager import force_stop_app
        force_stop_app(device_id, "threads")


if __name__ == "__main__":
    main()
