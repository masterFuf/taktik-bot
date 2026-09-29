"""TikTok automation workflow-test runners.

Not wired to production — see `not_wired` for why and for what each one must call.
"""

from bridges.tools.lab.workflow_test.execution.not_wired import not_wired


def run_tiktok_automation(conn, device, ipc, workflow_type, target, limits, probabilities, delays):
    return not_wired(ipc, workflow_type, "bridges.tiktok.automation.tiktok_bridge (the bridge that production actually runs)")
