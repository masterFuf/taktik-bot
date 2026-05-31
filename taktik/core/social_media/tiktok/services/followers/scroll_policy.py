"""Legacy scroll fallback policy for TikTok followers lists."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FollowersScrollDecision:
    attempts: int
    total_visited: int
    visited_ratio: float
    remaining: int | None
    reason: str


def calculate_legacy_followers_scroll_attempts(
    *,
    target_followers_count: int,
    already_visited_count: int,
    profiles_visited: int,
) -> FollowersScrollDecision:
    """Return the legacy scroll attempts used after no visible new row is found."""
    total_visited = max(0, already_visited_count) + max(0, profiles_visited)

    if target_followers_count > 0:
        visited_ratio = total_visited / target_followers_count
        remaining = target_followers_count - total_visited

        if visited_ratio >= 0.9:
            return FollowersScrollDecision(5, total_visited, visited_ratio, remaining, "ratio_90")
        if visited_ratio >= 0.7:
            return FollowersScrollDecision(10, total_visited, visited_ratio, remaining, "ratio_70")
        if visited_ratio >= 0.5:
            return FollowersScrollDecision(15, total_visited, visited_ratio, remaining, "ratio_50")
        return FollowersScrollDecision(20, total_visited, visited_ratio, remaining, "ratio_low")

    if total_visited > 0:
        if total_visited < 50:
            return FollowersScrollDecision(15, total_visited, 0.0, None, "visited_lt_50")
        if total_visited < 100:
            return FollowersScrollDecision(10, total_visited, 0.0, None, "visited_lt_100")
        return FollowersScrollDecision(5, total_visited, 0.0, None, "visited_gte_100")

    return FollowersScrollDecision(3, total_visited, 0.0, None, "no_data")


def get_visited_ratio(
    *,
    target_followers_count: int,
    already_visited_count: int,
    profiles_visited: int,
) -> float:
    """Return visited/total ratio capped at 1.0, or 0.0 when total is unknown."""
    if target_followers_count <= 0:
        return 0.0

    total_visited = max(0, already_visited_count) + max(0, profiles_visited)
    return min(total_visited / target_followers_count, 1.0)
