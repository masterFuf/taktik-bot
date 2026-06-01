"""Public facade for Instagram compat workflow diagnostic runners."""

from bridges.compat.diagnostics.runtime.instagram_workflows import (
    run_instagram_dm,
    run_instagram_publish,
    run_instagram_scraping,
    run_instagram_smart_comment,
)


__all__ = [
    "run_instagram_dm",
    "run_instagram_publish",
    "run_instagram_scraping",
    "run_instagram_smart_comment",
]
