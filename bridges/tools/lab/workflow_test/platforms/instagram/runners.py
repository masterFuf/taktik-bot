"""Public facade for Instagram compat workflow diagnostic runners."""

from bridges.tools.lab.workflow_test.platforms.instagram.workflows import (
    run_instagram_dm,
    run_instagram_publish,
    run_instagram_scraping,
)


__all__ = [
    "run_instagram_dm",
    "run_instagram_publish",
    "run_instagram_scraping",
]
