"""Public facade for Instagram automation compat diagnostic helpers."""

from bridges.compat.diagnostics.runtime.workflow_test.platforms.instagram.automation_config import build_workflow_payload
from bridges.compat.diagnostics.runtime.workflow_test.platforms.instagram.automation_instrumentation import trace_workflow_steps


__all__ = ["build_workflow_payload", "trace_workflow_steps"]
