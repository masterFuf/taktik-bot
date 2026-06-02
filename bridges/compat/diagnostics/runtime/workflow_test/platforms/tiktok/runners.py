"""Public facade for TikTok compat workflow diagnostic runners."""

from bridges.compat.diagnostics.runtime.workflow_test.platforms.tiktok.workflows import (
    run_tiktok_automation,
    run_tiktok_dm,
    run_tiktok_publish,
    run_tiktok_scraping,
    run_tiktok_unfollow,
)


__all__ = [
    "run_tiktok_automation",
    "run_tiktok_dm",
    "run_tiktok_publish",
    "run_tiktok_scraping",
    "run_tiktok_unfollow",
]
