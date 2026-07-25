"""TikTok DM workflow-test runners.

Not wired to production — see `not_wired` for why and for what each one must call.
"""

from bridges.compat.diagnostics.runtime.workflow_test.execution.not_wired import not_wired


def run_tiktok_dm(conn, device, ipc, workflow_type, limits, delays):
    return not_wired(ipc, workflow_type, "bridges.tiktok.engagement.dm_outreach (bridge runtime)")
