"""Instagram scraping workflow-test runners.

Not wired to production — see `not_wired` for why and for what each one must call.
"""

from bridges.compat.diagnostics.runtime.workflow_test.execution.not_wired import not_wired


def run_instagram_scraping(conn, device, ipc, workflow_type, target, limits, delays):
    return not_wired(ipc, workflow_type, "bridges.instagram.scraping.runtime.runner.run_scraping_bridge (CLI-shaped: takes argv)")
