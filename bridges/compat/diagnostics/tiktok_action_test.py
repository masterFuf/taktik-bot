"""
TikTok Action Test Bridge: manual action testing from the Debug Panel.

Outputs JSON lines to stdout:
  {"type": "log", "level": "info|debug|warning|error", "message": "..."}
  {"type": "result", "success": true|false, "message": "...", "selector_traces": [...]}
"""

from bridges.compat.diagnostics.actions.tiktok import (
    ACTION_REGISTRY,
    register_actions,
)
from bridges.compat.diagnostics.runtime.action_runner import run_action_test_bridge
from bridges.compat.diagnostics.runtime.bundles import (
    build_tiktok_action_bundle,
    create_tiktok_device_facade,
)
from bridges.compat.diagnostics.runtime.events import (
    configure_logger,
    configure_stdout,
)


configure_stdout()
configure_logger()
register_actions()


def main():
    run_action_test_bridge(
        ACTION_REGISTRY,
        create_tiktok_device_facade,
        build_tiktok_action_bundle,
    )


if __name__ == "__main__":
    main()
