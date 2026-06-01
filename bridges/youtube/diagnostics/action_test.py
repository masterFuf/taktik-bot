"""
YouTube Action Test Bridge: manual action testing from the Debug Panel.

Outputs JSON lines to stdout:
  {"type": "log", "level": "info|debug|warning|error", "message": "..."}
  {"type": "result", "success": true|false, "message": "..."}
"""

import sys

from bridges.youtube.diagnostics.actions import register_actions
from bridges.youtube.diagnostics.runtime.action_runner import run_youtube_action_test
from bridges.youtube.diagnostics.runtime.events import configure_logger, configure_stdout


configure_stdout()
configure_logger()
register_actions()


def main() -> None:
    run_youtube_action_test(sys.argv)


if __name__ == "__main__":
    main()
