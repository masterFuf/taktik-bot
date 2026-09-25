#!/usr/bin/env python3
"""
Desktop Bridge for TAKTIK Bot
This script allows the TAKTIK Desktop app to launch bot sessions programmatically.

`desktop_bridge <config.json>` runs one Instagram automation session (`DesktopBridge`, which calls
the core launcher shared with the CLI). `desktop_bridge --debug --mode <analyze|detect> --device
<serial>` runs the desktop's debug tooling instead.
"""

import sys
import os
import logging

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if bot_dir not in sys.path:
    sys.path.insert(0, bot_dir)

from bridges.common.runtime.entrypoint import run_bridge_main
from bridges.instagram.automation.runtime.bridge import DesktopBridge
from bridges.instagram.automation.runtime.input import load_debug_config
from bridges.instagram.diagnostics.debug import DebugBridge
from bridges.instagram.runtime.ipc import (
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


def _desktop_bridge(config: dict) -> DesktopBridge:
    # The desktop's debug console has always shown where the run's config came from.
    send_log("debug", f"Loaded config from file: {sys.argv[1]}")
    return DesktopBridge(config)


def _run_debug() -> int:
    try:
        return DebugBridge(load_debug_config()).run()
    except Exception as e:
        send_error(f"Bridge error: {str(e)}")
        logger.exception("Bridge error")
        return 1


def main():
    """Main entry point."""
    # Setup stats IPC callback before any workflow runs
    setup_stats_callback()

    if len(sys.argv) >= 2 and sys.argv[1] == "--debug":
        sys.exit(_run_debug())

    run_bridge_main(_desktop_bridge, usage="desktop_bridge <config.json>")


if __name__ == "__main__":
    main()
