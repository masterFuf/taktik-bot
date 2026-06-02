"""Public facade for Instagram automation compat diagnostic helpers."""

from bridges.compat.diagnostics.runtime.workflow_test.platforms.instagram.automation_config import build_workflow_config
from bridges.compat.diagnostics.runtime.workflow_test.platforms.instagram.automation_instrumentation import instrument_workflow_runner


__all__ = ["build_workflow_config", "instrument_workflow_runner"]
