"""TikTok scraping workflow-test runners.

Not wired to production — see `not_wired` for why and for what each one must call.
"""

from bridges.tools.lab.workflow_test.execution.not_wired import not_wired


def run_tiktok_scraping(conn, device, ipc, workflow_type, target, limits, delays):
    return not_wired(ipc, workflow_type, "bridges.tiktok.scraping.tiktok_scraping_bridge (bridge runtime)")
