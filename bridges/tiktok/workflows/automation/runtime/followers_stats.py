"""Stats and callback helpers for the TikTok Followers bridge runner."""

from typing import Any, Dict

from bridges.tiktok.runtime.ipc import logger, send_action, send_message, send_pause


def create_total_stats() -> Dict[str, int]:
    """Create the aggregate stats payload expected by the historical bridge contract."""
    return {
        "followers_seen": 0,
        "profiles_visited": 0,
        "posts_watched": 0,
        "likes": 0,
        "favorites": 0,
        "follows": 0,
        "already_friends": 0,
        "skipped": 0,
        "known_usernames_seen": 0,
        "new_usernames_seen": 0,
        "consecutive_known_usernames": 0,
        "errors": 0,
    }


def merge_live_stats(
    total_stats: Dict[str, Any],
    stats_dict: Dict[str, Any],
    current_target: str,
    target_idx: int,
    total_targets: int,
) -> Dict[str, Any]:
    """Merge current target live stats with already-completed target totals."""
    return {
        "followers_seen": total_stats["followers_seen"] + stats_dict.get("followers_seen", 0),
        "profiles_visited": total_stats["profiles_visited"] + stats_dict.get("profiles_visited", 0),
        "posts_watched": total_stats["posts_watched"] + stats_dict.get("posts_watched", 0),
        "likes": total_stats["likes"] + stats_dict.get("likes", 0),
        "favorites": total_stats["favorites"] + stats_dict.get("favorites", 0),
        "follows": total_stats["follows"] + stats_dict.get("follows", 0),
        "already_friends": total_stats["already_friends"] + stats_dict.get("already_friends", 0),
        "skipped": total_stats["skipped"] + stats_dict.get("skipped", 0),
        "known_usernames_seen": total_stats["known_usernames_seen"] + stats_dict.get("known_usernames_seen", 0),
        "new_usernames_seen": total_stats["new_usernames_seen"] + stats_dict.get("new_usernames_seen", 0),
        "consecutive_known_usernames": stats_dict.get("consecutive_known_usernames", 0),
        "errors": total_stats["errors"] + stats_dict.get("errors", 0),
        "current_target": current_target,
        "target_index": target_idx,
        "total_targets": total_targets,
    }


def record_target_stats(total_stats: Dict[str, Any], stats) -> None:
    """Accumulate a completed target stats object into the multi-target total."""
    total_stats["followers_seen"] += stats.followers_seen
    total_stats["profiles_visited"] += stats.profiles_visited
    total_stats["posts_watched"] += stats.posts_watched
    total_stats["likes"] += stats.likes
    total_stats["favorites"] += stats.favorites
    total_stats["follows"] += stats.follows
    total_stats["already_friends"] += stats.already_friends
    total_stats["skipped"] += stats.skipped
    total_stats["known_usernames_seen"] += stats.known_usernames_seen
    total_stats["new_usernames_seen"] += stats.new_usernames_seen
    total_stats["consecutive_known_usernames"] = stats.consecutive_known_usernames
    total_stats["errors"] += stats.errors


def wire_followers_callbacks(
    workflow,
    total_stats: Dict[str, Any],
    current_target: str,
    target_idx: int,
    total_targets: int,
) -> None:
    """Wire live bridge callbacks for one Followers workflow instance."""

    def on_action(action_info):
        send_action(action_info.get("action", "unknown"), action_info.get("target", ""))
        logger.info(f"🎯 Action: {action_info.get('action')} on @{action_info.get('target', '')}")

    def on_stats(stats_dict):
        send_message(
            "followers_stats",
            stats=merge_live_stats(total_stats, stats_dict, current_target, target_idx, total_targets),
        )

    def on_pause(duration: int):
        send_pause(duration)
        logger.info(f"⏸️ Taking a break for {duration}s")

    workflow.set_on_action_callback(on_action)
    workflow.set_on_stats_callback(on_stats)
    workflow.set_on_pause_callback(on_pause)
