"""Threads feed workflow runner used by the bridge dispatcher."""

from bridges.threads.base import logger, send_error, send_log, send_status
from bridges.threads.workflows.runtime.events import build_threads_callbacks, emit_threads_completion


def run_feed(config: dict) -> bool:
    """Threads Feed & Interact workflow."""
    from taktik.core.social_media.threads.workflows import (
        ActionProbabilities,
        FeedInteractConfig,
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

    send_log(
        "info",
        f"[threads:feed] device={device_id} max={feed_cfg.max_profiles} "
        f"probs(follow={feed_cfg.actions.follow}% like={feed_cfg.actions.like}% "
        f"repost={feed_cfg.actions.repost}% comment={feed_cfg.actions.comment}%)",
    )
    send_status("running", f"Threads feed workflow on {device_id}")

    try:
        stats = run_feed_and_interact(feed_cfg, **build_threads_callbacks())
    except Exception as exc:  # noqa: BLE001
        send_error(f"Threads feed workflow crashed: {exc}", error_code="threads.workflow_crash")
        logger.exception("Threads feed workflow crashed")
        return False

    emit_threads_completion("Threads feed workflow", stats)
    return stats.errors == 0 or (stats.follows + stats.likes + stats.reposts) > 0
