"""Public facade for Instagram automation compat diagnostic helpers."""

from bridges.tools.lab.workflow_test.platforms.instagram.automation_config import build_workflow_payload
from bridges.tools.lab.workflow_test.platforms.instagram.automation_instrumentation import trace_workflow_steps


__all__ = ["build_workflow_payload", "trace_workflow_steps"]
