"""Instagram DM workflow-test runners.

Not wired to production — see `not_wired` for why and for what each one must call.
"""

from bridges.compat.diagnostics.runtime.workflow_test.execution.not_wired import not_wired


def run_instagram_dm(conn, device, ipc, workflow_type, limits, delays):
    return not_wired(ipc, workflow_type, "bridges.instagram.engagement.runtime.dm.bridge.DMBridge (reader/sender mixins)")
