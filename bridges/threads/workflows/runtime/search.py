"""Threads search workflow runner used by the bridge dispatcher."""

from bridges.threads.base import logger, send_error, send_log, send_status
from bridges.threads.workflows.runtime.events import build_threads_callbacks, emit_threads_completion


def run_follow(config: dict) -> bool:
    """Real Threads Search-and-Interact workflow (MVP)."""
    from taktik.core.social_media.threads.workflows import (
        ActionProbabilities,
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

    try:
        stats = run_search_and_interact(interact_cfg, **build_threads_callbacks())
    except Exception as exc:  # noqa: BLE001
        send_error(f"Threads search workflow crashed: {exc}", error_code="threads.workflow_crash")
        logger.exception("Threads search workflow crashed")
        return False

    emit_threads_completion("Threads search workflow", stats)
    return stats.errors == 0 or (stats.follows + stats.likes + stats.reposts) > 0
