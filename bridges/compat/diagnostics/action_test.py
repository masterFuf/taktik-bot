"""
Action Test Bridge: manual Instagram action testing from the Debug Panel.

Outputs JSON lines to stdout:
  {"type": "log", "level": "info|debug|warning|error", "message": "..."}
  {"type": "result", "success": true|false, "message": "..."}
"""

from bridges.compat.diagnostics.actions.instagram import (
    ACTION_REGISTRY,
    register_actions,
)
from bridges.compat.diagnostics.runtime.action_test.runner import run_action_test_bridge
from bridges.compat.diagnostics.runtime.action_test.bundles import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
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
        create_instagram_device_facade,
        build_instagram_action_bundle,
    )


if __name__ == "__main__":
    main()
