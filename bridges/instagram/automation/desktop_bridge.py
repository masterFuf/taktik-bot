#!/usr/bin/env python3
"""
Desktop Bridge for TAKTIK Bot
This script allows the TAKTIK Desktop app to launch bot sessions programmatically.

`desktop_bridge <config.json>` runs one Instagram automation session (`DesktopBridge`, which calls
the core launcher shared with the CLI). A config with `debugMode: true` (`mode`: analyze or
detect, `deviceId`) runs the desktop's debug tooling instead.

The launcher reads the session's payload before it asks the bridge for the phone (`connect`, where
the bridge connects, rotates the IP and starts the media capture): a setting out of its bounds, or a
workflow this bridge does not serve, ends on the run's error line with nothing connected, rotated or
stopped (`DesktopBridge`).
"""

import sys
import os
import logging

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.entrypoint import loaded_config_path, run_bridge_main
from bridges.instagram.automation.bridge import DesktopBridge
from bridges.instagram.automation.debug import DebugBridge
from bridges.instagram.common.ipc import send_log, setup_stats_callback

# Configure logging for desktop integration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def _desktop_bridge(config: dict):
    if config.get("debugMode"):
        # The debug tooling says its own failures (`DebugBridge.run`); what escapes it is the
        # entry's crash line.
        return DebugBridge(config)
    # The desktop's debug console has always shown where the run's config came from.
    send_log("debug", f"Loaded config from file: {loaded_config_path()}")
    return DesktopBridge(config)


def main():
    """Main entry point."""
    # Setup stats IPC callback before any workflow runs
    setup_stats_callback()

    run_bridge_main(_desktop_bridge, usage="desktop_bridge <config.json>")


if __name__ == "__main__":
    main()
