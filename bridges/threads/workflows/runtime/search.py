"""Threads search workflow runner used by the bridge dispatcher."""

from bridges.threads.base import (
    logger,
    send_error,
    send_log,
    send_status,
    send_threads_action,
    send_threads_profile_visit,
    send_threads_stats,
)


def run_follow(config: dict) -> bool:
    """Real Threads Search-and-Interact workflow (MVP)."""
    from taktik.core.social_media.threads.workflows import (
        ActionProbabilities,
        InteractStats,
        ProfileFilters,
        SearchInteractConfig,
        run_search_and_interact,
    )

    device_id = config.get("deviceId", "unknown")

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

    send_log(
        "info",
        f"[threads:search] device={device_id} query={query!r} "
        f"max={interact_cfg.max_profiles} "
        f"probs(follow={interact_cfg.actions.follow}% like={interact_cfg.actions.like}% "
        f"repost={interact_cfg.actions.repost}% comment={interact_cfg.actions.comment}%)",
    )
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
    except Exception as exc:  # noqa: BLE001
        send_error(f"Threads search workflow crashed: {exc}", error_code="threads.workflow_crash")
        logger.exception("Threads search workflow crashed")
        return False

    send_threads_stats(**stats.as_dict())
    summary = (
        f"visited={stats.profiles_visited} follows={stats.follows} "
        f"likes={stats.likes} reposts={stats.reposts} errors={stats.errors}"
    )
    send_status("completed", f"Threads search workflow finished — {summary}")
    return stats.errors == 0 or (stats.follows + stats.likes + stats.reposts) > 0
