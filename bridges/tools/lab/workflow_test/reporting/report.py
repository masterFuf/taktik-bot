"""Final report assembly for compat workflow diagnostics."""

import math


def build_workflow_report(
    tracer,
    *,
    workflow_type: str,
    target: str,
    workflow_success: bool,
    workflow_error: str | None,
    elapsed_s: float,
    limits: dict,
    probs: dict,
    session_duration: int,
    delays: dict,
    app_name: str,
    version: str,
    device_id: str,
    last_stats: dict | None,
) -> tuple[dict, int, str, str]:
    """Build the final compatibility report and status metadata."""
    report = tracer.report()

    expected_results = _build_expected_results(limits, probs)
    actual_results = _build_actual_results(last_stats)

    functional_success = workflow_success
    functional_notes = []
    if expected_results["profiles"] > 0 and actual_results["profiles_interacted"] == 0:
        functional_success = False
        functional_notes.append("No profiles interacted")
    if expected_results["likes"] > 0 and actual_results["likes"] == 0:
        functional_success = False
        functional_notes.append("No likes performed")

    report["workflow"] = {
        "type": workflow_type,
        "target": target,
        "success": workflow_success,
        "error": workflow_error,
        "elapsed_seconds": elapsed_s,
        "limits": limits,
        "probabilities": probs,
        "session_duration": session_duration,
        "delays": delays,
    }
    report["expected_results"] = expected_results
    report["actual_results"] = actual_results
    report["functional"] = {
        "success": functional_success,
        "notes": functional_notes,
    }
    report["app"] = app_name
    report["version"] = version
    report["device_id"] = device_id

    score = report.get("compatibility_score", 0)
    status = "passed" if score >= 80 and workflow_success else "failed"
    status_message = (
        f"Score: {score}% | {report['unique_xpaths_found']}/{report['unique_xpaths']} selectors | {elapsed_s}s"
    )
    return report, score, status, status_message


def _build_expected_results(limits: dict, probs: dict) -> dict:
    max_profiles = limits.get("maxProfiles", limits.get("maxInteractions", limits.get("maxUnfollows", 0)))
    max_likes_pp = limits.get("maxLikesPerProfile", 0)
    like_pct = probs.get("like", 0)
    follow_pct = probs.get("follow", 0)
    comment_pct = probs.get("comment", 0)
    story_pct = probs.get("watchStories", 0)

    return {
        "profiles": max_profiles,
        "likes": math.ceil(max_profiles * max_likes_pp * like_pct / 100) if like_pct and max_likes_pp else 0,
        "follows": math.ceil(max_profiles * follow_pct / 100) if follow_pct else 0,
        "comments": math.ceil(max_profiles * comment_pct / 100) if comment_pct else 0,
        "stories": math.ceil(max_profiles * story_pct / 100) if story_pct else 0,
    }


def _build_actual_results(last_stats: dict | None) -> dict:
    if not last_stats:
        return {
            "profiles_visited": 0,
            "profiles_interacted": 0,
            "likes": 0,
            "follows": 0,
            "comments": 0,
            "stories_watched": 0,
            "errors": 0,
        }

    return {
        "profiles_visited": last_stats.get("profiles_visited", 0),
        "profiles_interacted": last_stats.get("profiles_interacted", 0),
        "likes": last_stats.get("likes", 0),
        "follows": last_stats.get("follows", 0),
        "comments": last_stats.get("comments", 0),
        "stories_watched": last_stats.get("stories_watched", 0),
        "errors": last_stats.get("errors", 0),
    }


__all__ = ["build_workflow_report"]

