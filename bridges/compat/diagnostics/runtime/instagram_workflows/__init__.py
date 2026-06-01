"""Instagram workflow-test runner families for compat diagnostics."""

from bridges.compat.diagnostics.runtime.instagram_workflows.dm import run_instagram_dm
from bridges.compat.diagnostics.runtime.instagram_workflows.publish import run_instagram_publish
from bridges.compat.diagnostics.runtime.instagram_workflows.scraping import run_instagram_scraping
from bridges.compat.diagnostics.runtime.instagram_workflows.smart_comment import run_instagram_smart_comment


__all__ = [
    "run_instagram_dm",
    "run_instagram_publish",
    "run_instagram_scraping",
    "run_instagram_smart_comment",
]
