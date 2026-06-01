"""Public facade for Instagram observability hooks."""

from bridges.compat.diagnostics.runtime.workflow_observability_instagram_hooks import setup_instagram_action_hooks
from bridges.compat.diagnostics.runtime.workflow_observability_instagram_screens import infer_instagram_screen_from_log


__all__ = ["infer_instagram_screen_from_log", "setup_instagram_action_hooks"]
