"""Why a run ended: the closed sets the bot sends, one catalogue per vocabulary.

Each is a named `OneOf`: the app gets one union type per catalogue, and every line that carries a
reason refers to it. The values are what the bot emits today, none renamed; the tests hold each
set to the code that produces it (`tests/unit/app/contract/test_workflow_contract_stop_reasons.py`).
"""

from __future__ import annotations

from dataclasses import replace

from .schema import OneOf

#: The run's stop latch (`taktik/core/shared/diagnostics/run_halt.py`): what a run can no longer do,
#: read by every loop that decides to go on. A run stopped by it says so with this code.
RUN_HALT_CODE = OneOf(
    ("device_disconnected", "target_app_crashed", "action_blocked", "desktop_gone"),
    name="RunHaltCode",
    doc="Why the stop latch stopped the run (`run_halt`).",
)

#: `session_stop.reason_code` of an Instagram run: the factories of
#: `social_media/instagram/workflows/management/session/stop_reasons.py`.
INSTAGRAM_STOP_REASON_CODE = OneOf(
    (
        # ok: a cap reached
        "duration_cap", "profiles_cap", "follows_cap", "likes_cap", "daily_budget", "unfollows_cap",
        "daily_unfollow_budget", "session_action_cap", "posts_cap",
        # ok: nothing left to process
        "end_of_list", "end_of_list_repeated", "end_of_list_suggestions", "no_new_profiles",
        "known_streak", "scroll_budget", "scroll_streak", "sources_exhausted", "no_valid_post",
        "no_new_post", "posts_examined_cap", "no_unfollow_candidates",
        # ok: done
        "completed",
        # failed: go and look
        "action_blocked", "unfollow_unconfirmed", "no_account", "stuck_at_top", "navigation_lost",
        "list_unavailable", "empty_plan", "no_targets", "daily_budget_unreadable", "crashed",
        "device_disconnected", "target_app_crashed", "desktop_gone",
        # manual
        "manual_stop",
    ),
    name="InstagramStopReasonCode",
    doc="Why an Instagram session ended (`session_stop.reason_code`).",
)

#: `completion_reason` / `stop_reason` of a TikTok run: set by the workflows of
#: `social_media/tiktok/**`, plus the stop latch's codes they copy.
TIKTOK_COMPLETION_REASON = OneOf(
    (
        # a cap reached
        "max_profiles_reached", "max_likes_reached", "max_follows_reached", "max_scrolls_reached",
        "max_duration_reached", "max_consecutive_known_usernames",
        # nothing left to process
        "no_more_followers", "list_exhausted", "known_reached",
        # done, or the workflow cannot say
        "completed", "unknown",
        # failed
        "navigation_failed", "list_unreachable", "no_targets", "no_account", "feed_stuck",
        "unfollow_unconfirmed", "error",
        # the stop latch
        *RUN_HALT_CODE.values,
        # manual
        "stopped_by_user",
    ),
    name="TikTokCompletionReason",
    doc="Why a TikTok run ended (`completion_reason`, `stop_reason`).",
)

#: The counters of a TikTok run carry the reason from the start, empty until the run ends.
TIKTOK_COMPLETION_REASON_OR_NONE = replace(TIKTOK_COMPLETION_REASON, empty=True)

#: `scraping_result.completionReason` of an Instagram scraping: the verdict of
#: `social_media/instagram/workflows/scraping/outcome.py`.
INSTAGRAM_SCRAPING_COMPLETION_REASON = OneOf(
    ("completed", "nothing_to_scrape", "target_never_reached"),
    name="InstagramScrapingCompletionReason",
    doc="How an Instagram scraping ended: its surface reached or not, profiles or none.",
)

#: Every catalogue, for the generator and the tests.
CATALOGUES = (
    RUN_HALT_CODE,
    INSTAGRAM_STOP_REASON_CODE,
    TIKTOK_COMPLETION_REASON,
    INSTAGRAM_SCRAPING_COMPLETION_REASON,
)

__all__ = [
    "CATALOGUES",
    "INSTAGRAM_SCRAPING_COMPLETION_REASON",
    "INSTAGRAM_STOP_REASON_CODE",
    "RUN_HALT_CODE",
    "TIKTOK_COMPLETION_REASON",
    "TIKTOK_COMPLETION_REASON_OR_NONE",
]
