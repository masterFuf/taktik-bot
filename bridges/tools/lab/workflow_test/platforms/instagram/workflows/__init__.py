"""Instagram runner families of the workflow bench of the Lab."""

from bridges.tools.lab.workflow_test.platforms.instagram.workflows.dm import run_instagram_dm
from bridges.tools.lab.workflow_test.platforms.instagram.workflows.publish import run_instagram_publish
from bridges.tools.lab.workflow_test.platforms.instagram.workflows.scraping import run_instagram_scraping


__all__ = [
    "run_instagram_dm",
    "run_instagram_publish",
    "run_instagram_scraping",
]
