"""Threads feed workflow runner used by the bridge dispatcher."""

from bridges.threads.base import (
    logger,
    send_error,
    send_log,
    send_status,
    send_threads_action,
    send_threads_profile_visit,
    send_threads_stats,
)


def run_feed(config: dict) -> bool:
    """Threads Feed & Interact workflow."""
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

    send_log(
        "info",
        f"[threads:feed] device={device_id} max={feed_cfg.max_profiles} "
        f"probs(follow={feed_cfg.actions.follow}% like={feed_cfg.actions.like}% "
        f"repost={feed_cfg.actions.repost}% comment={feed_cfg.actions.comment}%)",
    )
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
    summary = (
        f"visited={stats.profiles_visited} follows={stats.follows} "
        f"likes={stats.likes} reposts={stats.reposts} errors={stats.errors}"
    )
    send_status("completed", f"Threads feed workflow finished \u2014 {summary}")
    return stats.errors == 0 or (stats.follows + stats.likes + stats.reposts) > 0
