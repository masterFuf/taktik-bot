"""Instagram publish workflow-test runners.

Not wired to production — see `not_wired` for why and for what each one must call.
"""

from bridges.compat.diagnostics.runtime.workflow_test.execution.not_wired import not_wired


def run_instagram_publish(conn, device, ipc, workflow_type):
    return not_wired(ipc, workflow_type, "taktik.core.social_media.instagram.workflows.publish.post_workflow.InstagramPostWorkflow")
