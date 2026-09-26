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
from bridges.common.runtime.entrypoint import CONFIG_ERROR, MISSING_CONFIG, run_bridge_main
from bridges.compat.diagnostics.runtime.action_test.runner import action_test_run, report_action_test_entry_error
from bridges.compat.diagnostics.runtime.action_test.bundles import (
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
    run_bridge_main(
        action_test_run(ACTION_REGISTRY, create_tiktok_device_facade, build_tiktok_action_bundle),
        usage="tiktok_action_test_bridge <config.json>",
        report_error=report_action_test_entry_error,
        messages={MISSING_CONFIG: "No config file provided", CONFIG_ERROR: "Failed to read config: {error}"},
        catch_crashes=False,
    )


if __name__ == "__main__":
    main()
