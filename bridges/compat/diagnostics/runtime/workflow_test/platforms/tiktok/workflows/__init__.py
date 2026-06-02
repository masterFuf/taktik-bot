"""TikTok workflow-test runner families for compat diagnostics."""

from bridges.compat.diagnostics.runtime.workflow_test.platforms.tiktok.workflows.automation import run_tiktok_automation
from bridges.compat.diagnostics.runtime.workflow_test.platforms.tiktok.workflows.dm import run_tiktok_dm
from bridges.compat.diagnostics.runtime.workflow_test.platforms.tiktok.workflows.publish import run_tiktok_publish
from bridges.compat.diagnostics.runtime.workflow_test.platforms.tiktok.workflows.scraping import run_tiktok_scraping
from bridges.compat.diagnostics.runtime.workflow_test.platforms.tiktok.workflows.unfollow import run_tiktok_unfollow


__all__ = [
    "run_tiktok_automation",
    "run_tiktok_dm",
    "run_tiktok_publish",
    "run_tiktok_scraping",
    "run_tiktok_unfollow",
]
