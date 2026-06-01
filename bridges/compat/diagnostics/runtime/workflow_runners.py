"""Public facade for compat workflow diagnostic runners."""

from bridges.compat.diagnostics.runtime.workflow_runners_instagram import (
    run_instagram_dm,
    run_instagram_publish,
    run_instagram_scraping,
    run_instagram_smart_comment,
)
from bridges.compat.diagnostics.runtime.workflow_runners_tiktok import (
    run_tiktok_automation,
    run_tiktok_dm,
    run_tiktok_publish,
    run_tiktok_scraping,
    run_tiktok_unfollow,
)


__all__ = [
    "run_instagram_dm",
    "run_instagram_publish",
    "run_instagram_scraping",
    "run_instagram_smart_comment",
    "run_tiktok_automation",
    "run_tiktok_dm",
    "run_tiktok_publish",
    "run_tiktok_scraping",
    "run_tiktok_unfollow",
]

