"""
YouTube Action Test Bridge: manual action testing from the Debug Panel.

Outputs JSON lines to stdout:
  {"type": "log", "level": "info|debug|warning|error", "message": "..."}
  {"type": "result", "success": true|false, "message": "..."}
"""

from bridges.youtube.diagnostics.actions import register_actions
from bridges.common.runtime.entrypoint import CONFIG_ERROR, MISSING_CONFIG, run_bridge_main
from bridges.youtube.diagnostics.runtime.action_runner import (
    YouTubeActionTestRun,
    report_youtube_action_entry_error,
)
from bridges.youtube.diagnostics.runtime.events import configure_logger, configure_stdout


configure_stdout()
configure_logger()
register_actions()


def main() -> None:
    run_bridge_main(YouTubeActionTestRun, usage="youtube_action_test_bridge <config.json>",
                    report_error=report_youtube_action_entry_error,
                    messages={MISSING_CONFIG: "No config file provided", CONFIG_ERROR: "Failed to read config: {error}"}, catch_crashes=False)


if __name__ == "__main__":
    main()
