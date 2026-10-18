#!/usr/bin/env python3
"""
Desktop Bridge for TAKTIK Bot
This script allows the TAKTIK Desktop app to launch bot sessions programmatically.

`desktop_bridge <config.json>` runs one Instagram automation session (`DesktopBridge`, which calls
the core launcher shared with the CLI). A config with `debugMode: true` (`mode`: analyze or
detect, `deviceId`) runs the desktop's debug tooling instead.

The bridge connects to the phone and rotates its IP before it hands the phone to the launcher, so
the launcher's reader reads the session's payload first, at the entry (`read_payload`): a setting
out of its bounds, or a workflow this bridge does not serve, ends on the run's error line with
nothing connected, rotated or stopped.
"""

import sys
import os
import logging

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.entrypoint import REFUSED, loaded_config_path, report_entry_error, run_bridge_main
from bridges.instagram.automation.bridge import DesktopBridge
from bridges.instagram.automation.debug import DebugBridge
from bridges.instagram.automation.events import send_instagram_run_error
from bridges.instagram.common.ipc import (
    logger,
    send_error,
    send_log,
    setup_stats_callback,
)

# Configure logging for desktop integration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class _DebugRun:
    """The desktop's debug tooling, with its own error event."""

    def __init__(self, config: dict):
        self.config = config

    def run(self) -> int:
        try:
            return DebugBridge(self.config).run()
        except Exception as e:
            send_error(f"Bridge error: {str(e)}")
            logger.exception("Bridge error")
            return 1


def _desktop_bridge(config: dict):
    if config.get("debugMode"):
        return _DebugRun(config)
    # The desktop's debug console has always shown where the run's config came from.
    send_log("debug", f"Loaded config from file: {loaded_config_path()}")
    return DesktopBridge(config)


def _read_session_payload(config: dict) -> None:
    """The launcher's reader on the session's payload, before the bridge is built. The debug
    tooling carries no session payload."""
    if config.get("debugMode"):
        return
    from taktik.core.social_media.instagram.workflows.automation.config_builder import (
        build_instagram_automation_config,
    )

    build_instagram_automation_config(config)


def _report_entry_error(message: str, reason: str) -> None:
    """An entry failure; a refused payload ends on the error line of a failed run, as it always has."""
    if reason == REFUSED:
        send_instagram_run_error(message)
        return
    report_entry_error(message, reason)


def main():
    """Main entry point."""
    # Setup stats IPC callback before any workflow runs
    setup_stats_callback()

    run_bridge_main(_desktop_bridge, usage="desktop_bridge <config.json>", read_payload=_read_session_payload,
                    report_error=_report_entry_error)


if __name__ == "__main__":
    main()
