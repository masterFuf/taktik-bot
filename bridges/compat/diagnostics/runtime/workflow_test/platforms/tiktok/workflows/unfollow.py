"""TikTok unfollow workflow-test runners.

Not wired to production — see `not_wired` for why and for what each one must call.
"""

from bridges.compat.diagnostics.runtime.workflow_test.execution.not_wired import not_wired


def run_tiktok_unfollow(conn, device, ipc, limits, delays):
    return not_wired(ipc, "tiktok_unfollow", "bridges.tiktok.automation.unfollow (bridge runtime)")
